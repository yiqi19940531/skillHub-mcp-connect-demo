import hashlib
import hmac
import secrets
import time

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
import jwt

from backend.app.errors import HubError, require
from backend.app.services.authorization import principal
from backend.app.storage.repository import atomic_write, now, uid

PASSWORDS = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
DUMMY_HASH = PASSWORDS.hash(secrets.token_urlsafe(24))
SCOPES = {"skills:read", "skills:write"}


def token_hash(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


class Identity:
    def __init__(self, hub):
        self.hub = hub
        self.repo, self.settings = hub.repo, hub.settings
        key_path = self.settings.data_dir / "secrets" / "jwt.key"
        with self.repo.transaction():
            if not key_path.exists():
                atomic_write(key_path, secrets.token_bytes(64))
            self.key = key_path.read_bytes()
        import os

        os.chmod(key_path, 0o600)
        os.chmod(key_path.parent, 0o700)
        self.attempts = {}

    def begin_boot(self):
        with self.repo.transaction() as tx:
            tx["tickets"].clear()
            tx["oauth_codes"].clear()
            tx["oauth_requests"].clear()

    def limit(self, key, count=20, seconds=60):
        current = time.monotonic()
        recent = [value for value in self.attempts.get(key, []) if current - value < seconds]
        require(len(recent) < count, "RATE_LIMITED", "请求过于频繁，请稍后重试", 429)
        recent.append(current)
        self.attempts[key] = recent
        if len(self.attempts) > 2000:
            self.attempts = {k: v for k, v in self.attempts.items() if v and current - v[-1] < seconds}

    def login(self, username, password, address="local"):
        self.limit("login:" + address + ":" + token_hash(username.casefold()), 8)
        raw, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        valid = False
        with self.repo.transaction() as tx:
            user = next(
                (u for u in tx["users"].values() if u["username"].casefold() == username.casefold()), None
            )
            try:
                valid = PASSWORDS.verify(user["password_hash"] if user else DUMMY_HASH, password)
            except VerificationError:
                pass
            if valid and user and not user["disabled"]:
                tx["sessions"][token_hash(raw)] = {
                    "user_id": user["user_id"],
                    "csrf_hash": token_hash(csrf),
                    "expires_at": int(time.time()) + self.settings.session_minutes * 60,
                    "epoch": user["auth_epoch"],
                    "revoked": False,
                    "created_at": now(),
                }
                tx.audit(user["user_id"], "web_login")
                user_id = user["user_id"]
            else:
                tx.audit("anonymous", "web_login", result="invalid_credentials", decision="deny")
                valid = False
        require(valid, "UNAUTHENTICATED", "账号或密码错误，或账号已停用", 401)
        return raw, csrf, user_id

    def session(self, raw):
        require(raw, "UNAUTHENTICATED", "请先登录", 401)
        state = self.repo.snapshot()
        session = state["sessions"].get(token_hash(raw))
        require(
            session and not session["revoked"] and session["expires_at"] > time.time(),
            "UNAUTHENTICATED",
            "会话已过期，请重新登录",
            401,
        )
        user = state["users"].get(session["user_id"])
        require(
            user and not user["disabled"] and session["epoch"] == user["auth_epoch"],
            "UNAUTHENTICATED",
            "会话已失效",
            401,
        )
        return user["user_id"], session

    def csrf(self, session, provided):
        require(
            provided and hmac.compare_digest(session["csrf_hash"], token_hash(provided)),
            "CSRF_INVALID",
            "页面校验已失效，请刷新后重试",
            403,
        )

    def logout(self, raw):
        if not raw:
            return
        with self.repo.transaction() as tx:
            session = tx["sessions"].get(token_hash(raw))
            if session:
                session["revoked"] = True
                tx.audit(session["user_id"], "web_logout")

    def validate_access(self, raw):
        try:
            claims = jwt.decode(
                raw,
                self.key,
                algorithms=["HS256"],
                audience=self.settings.resource,
                issuer=self.settings.base_url,
                options={"require": ["exp", "iat", "sub", "jti", "aud", "iss", "grant_id"]},
            )
            state = self.repo.snapshot()
            grant = state["oauth_grants"].get(claims["grant_id"])
            user = state["users"].get(claims["sub"])
            require(
                grant
                and user
                and not grant["revoked"]
                and not user["disabled"]
                and grant["user_id"] == user["user_id"]
                and grant["epoch"] == user["auth_epoch"]
                and claims["client_id"] == grant["client_id"]
                and claims["scope"] == grant["scope"],
                "UNAUTHENTICATED",
                "授权已失效",
                401,
            )
            return claims
        except (jwt.PyJWTError, KeyError, ValueError, TypeError) as exc:
            raise HubError("UNAUTHENTICATED", "访问令牌无效或过期", 401) from exc

    def issue_tokens(self, tx, grant):
        current = int(time.time())
        claims = {
            "iss": self.settings.base_url,
            "aud": self.settings.resource,
            "sub": grant["user_id"],
            "iat": current,
            "exp": current + self.settings.access_minutes * 60,
            "jti": uid("token"),
            "client_id": grant["client_id"],
            "grant_id": grant["grant_id"],
            "scope": grant["scope"],
        }
        refresh = secrets.token_urlsafe(48)
        tx["oauth_refresh"][token_hash(refresh)] = {
            "grant_id": grant["grant_id"],
            "used": False,
            "expires_at": current + self.settings.refresh_days * 86400,
            "created_at": now(),
        }
        return {
            "access_token": jwt.encode(claims, self.key, algorithm="HS256"),
            "token_type": "Bearer",
            "expires_in": self.settings.access_minutes * 60,
            "refresh_token": refresh,
            "scope": grant["scope"],
        }

    def grants(self, user_id):
        with self.repo.transaction() as tx:
            principal(tx, user_id)
            return [
                {
                    "grant_id": g["grant_id"],
                    "client_id": g["client_id"],
                    "scope": g["scope"],
                    "client_name": tx["oauth_clients"]
                    .get(g["client_id"], {})
                    .get("client_name", "MCP Client"),
                    "created_at": g["created_at"],
                    "revoked": g["revoked"],
                }
                for g in tx["oauth_grants"].values()
                if g["user_id"] == user_id
            ]

    def revoke_grant(self, user_id, grant_id):
        with self.repo.transaction() as tx:
            principal(tx, user_id)
            grant = tx["oauth_grants"].get(grant_id)
            require(grant and grant["user_id"] == user_id, "GRANT_NOT_FOUND", "授权记录不可访问", 404)
            grant["revoked"] = True
            for ticket in tx["tickets"].values():
                if ticket["user_id"] == user_id:
                    ticket["used"] = True
            tx.audit(user_id, "revoke_oauth_grant", grant_id)

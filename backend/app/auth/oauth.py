import base64
import hashlib
import hmac
import html
import re
import secrets
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from backend.app.auth.identity import SCOPES, token_hash
from backend.app.errors import HubError, require
from backend.app.services.authorization import principal
from backend.app.storage.repository import now, uid
from backend.app.security.headers import content_security_policy


def valid_redirect(uri):
    try:
        url = urlsplit(uri)
        port = url.port  # Validate an explicitly supplied port before storing it.
        return bool(
            url.hostname
            and re.fullmatch(r"[A-Za-z0-9.\[\]:-]+", url.netloc)
            and not any(c.isspace() or ord(c) < 32 for c in uri)
            and (port is None or port > 0)
            and not url.username
            and not url.password
            and not url.fragment
            and len(uri) <= 2048
            and (
                url.scheme == "https"
                or (url.scheme == "http" and url.hostname in {"127.0.0.1", "localhost", "::1"})
            )
        )
    except ValueError:
        return False


def redirect_matches(registered, requested):
    if not valid_redirect(requested):
        return False
    left, right = urlsplit(registered), urlsplit(requested)
    if (
        left.scheme == right.scheme == "http"
        and left.hostname == right.hostname
        and left.hostname in {"127.0.0.1", "::1"}
    ):
        return left.path == right.path and left.query == right.query
    return registered == requested


def oauth_redirect(uri, **parameters):
    url = urlsplit(uri)
    return urlunsplit(
        (url.scheme, url.netloc, url.path, urlencode(parse_qsl(url.query) + list(parameters.items())), "")
    )


def router_for(hub, identity):
    router = APIRouter()
    cfg = hub.settings

    def oauth_error(code, description, status=400):
        return JSONResponse(
            {"error": code, "error_description": description},
            status_code=status,
            headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
        )

    @router.get("/.well-known/oauth-protected-resource")
    @router.get("/.well-known/oauth-protected-resource/mcp")
    def resource_metadata():
        return {
            "resource": cfg.resource,
            "authorization_servers": [cfg.base_url],
            "scopes_supported": sorted(SCOPES),
            "bearer_methods_supported": ["header"],
            "resource_name": "Enterprise Skill Hub",
        }

    @router.get("/.well-known/oauth-authorization-server")
    def authorization_metadata():
        return {
            "issuer": cfg.base_url,
            "authorization_endpoint": cfg.base_url + "/oauth/authorize",
            "token_endpoint": cfg.base_url + "/oauth/token",
            "registration_endpoint": cfg.base_url + "/oauth/register",
            "revocation_endpoint": cfg.base_url + "/oauth/revoke",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "scopes_supported": sorted(SCOPES),
            "token_endpoint_auth_methods_supported": ["none"],
            "code_challenge_methods_supported": ["S256"],
            "authorization_response_iss_parameter_supported": True,
        }

    @router.post("/oauth/register")
    async def register(request: Request):
        identity.limit("register:" + (request.client.host if request.client else "local"), 30)
        try:
            data = await request.json()
            uris = data.get("redirect_uris", [])
            require(
                isinstance(uris, list)
                and 1 <= len(uris) <= 10
                and all(isinstance(u, str) and valid_redirect(u) for u in uris),
                "invalid_redirect_uri",
                "需要有效的 HTTPS 或 loopback 回调 URI",
            )
            require(
                data.get("token_endpoint_auth_method", "none") == "none",
                "invalid_client_metadata",
                "仅支持 public client",
            )
            require(
                set(data.get("grant_types", ["authorization_code", "refresh_token"]))
                <= {"authorization_code", "refresh_token"}
                and data.get("response_types", ["code"]) == ["code"],
                "invalid_client_metadata",
                "授权类型不受支持",
            )
            scopes = set(data.get("scope", "skills:read skills:write").split())
            require(scopes <= SCOPES and "skills:read" in scopes, "invalid_scope", "授权范围无效")
            name = data.get("client_name", "MCP Client")
            require(
                isinstance(name, str) and 0 < len(name) <= 100, "invalid_client_metadata", "客户端名称无效"
            )
            client_id = uid("client")
            record = {
                "client_id": client_id,
                "client_name": name,
                "redirect_uris": uris,
                "token_endpoint_auth_method": "none",
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
                "scope": " ".join(sorted(scopes)),
                "client_id_issued_at": hub.timestamp(),
                "created_at": now(),
            }
            with hub.repo.transaction() as tx:
                tx["oauth_clients"][client_id] = record
                tx.audit("anonymous", "oauth_client_register", client_id)
            return JSONResponse(record, status_code=201)
        except (ValueError, TypeError, AttributeError):
            return oauth_error("invalid_client_metadata", "客户端注册请求无效")
        except HubError as error:
            return oauth_error(error.code, error.message)

    @router.get("/oauth/authorize")
    def authorize(request: Request):
        params = dict(request.query_params)
        try:
            with hub.repo.transaction() as tx:
                request_id = params.get("request_id")
                if request_id:
                    pending = tx["oauth_requests"].get(request_id)
                    require(
                        pending and pending["expires_at"] > hub.timestamp(),
                        "invalid_request",
                        "授权请求已过期",
                    )
                else:
                    client = tx["oauth_clients"].get(params.get("client_id"))
                    require(client is not None, "invalid_client", "客户端尚未注册")
                    redirect = params.get("redirect_uri", "")
                    require(
                        any(redirect_matches(u, redirect) for u in client["redirect_uris"]),
                        "invalid_request",
                        "回调 URI 不匹配",
                    )
                    require(
                        params.get("response_type") == "code"
                        and params.get("code_challenge_method") == "S256"
                        and re.fullmatch(r"[A-Za-z0-9_-]{43}", params.get("code_challenge", "")),
                        "invalid_request",
                        "必须使用授权码与 PKCE S256",
                    )
                    require(
                        params.get("state") and len(params["state"]) <= 1024, "invalid_request", "state 必填"
                    )
                    require(params.get("resource") == cfg.resource, "invalid_target", "请求资源不匹配")
                    scopes = set(params.get("scope", "skills:read skills:write").split())
                    require(
                        scopes <= set(client["scope"].split()) and "skills:read" in scopes,
                        "invalid_scope",
                        "授权范围无效",
                    )
                    request_id = uid("authreq")
                    pending = {
                        "request_id": request_id,
                        "client_id": client["client_id"],
                        "redirect_uri": redirect,
                        "scope": " ".join(sorted(scopes)),
                        "state": params["state"],
                        "resource": cfg.resource,
                        "code_challenge": params["code_challenge"],
                        "expires_at": hub.timestamp() + 300,
                    }
                    tx["oauth_requests"][request_id] = pending
            try:
                user_id, session = identity.session(request.cookies.get("skillhub_session"))
            except HubError:
                return RedirectResponse(
                    "/app/login?" + urlencode({"next": "/oauth/authorize?request_id=" + request_id}), 303
                )
            state = hub.repo.snapshot()
            user, client = state["users"][user_id], state["oauth_clients"][pending["client_id"]]
            escape = html.escape
            csrf = request.cookies.get("skillhub_csrf", "")
            callback = urlsplit(pending["redirect_uri"])
            callback_origin = f"{callback.scheme}://{callback.netloc}"
            return HTMLResponse(
                f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>授权 · Skill Hub</title>
<style>body{{background:#f4f6fb;font:15px system-ui;color:#152136;display:grid;place-items:center;min-height:95vh}}main{{background:white;border:1px solid #e2e7ef;border-radius:24px;padding:40px;max-width:460px;box-shadow:0 12px 50px #24375612}}h1{{font-size:24px}}p{{line-height:1.8;color:#526078}}code{{overflow-wrap:anywhere}}button{{padding:12px 24px;border:0;border-radius:10px;background:#315de8;color:white;font:inherit;cursor:pointer}}button[value=deny]{{background:#eef1f7;color:#334155;margin-left:8px}}a{{color:#315de8}}</style></head>
<body><main><small>ENTERPRISE SKILL HUB</small><h1>授权连接你的技能库</h1><p>以 <b>{escape(user["display_name"])}</b>（{escape(user["username"])}）授权 <b>{escape(client["client_name"])}</b>。</p>
<p>范围：{escape(pending["scope"])}<br>客户端只能操作你有权访问的资源，审批仍需在 Web 完成。</p><p>回调地址：<code>{escape(pending["redirect_uri"])}</code></p>
<form method="post" action="/oauth/authorize"><input type="hidden" name="request_id" value="{escape(request_id)}"><input type="hidden" name="csrf" value="{escape(csrf)}"><button name="decision" value="approve">同意并连接</button><button name="decision" value="deny">拒绝</button></form>
<p><a href="/app/settings">管理账号与已授权连接</a></p></main></body></html>''',
                headers={"Content-Security-Policy": content_security_policy(callback_origin)},
            )
        except HubError as error:
            return oauth_error(error.code, error.message)

    @router.post("/oauth/authorize")
    async def consent(request: Request):
        try:
            user_id, session = identity.session(request.cookies.get("skillhub_session"))
            form = await request.form()
            identity.csrf(session, form.get("csrf"))
            require(
                # Native-app authorization navigation can have an opaque Origin ("null").
                # The session-bound, 256-bit CSRF token above remains mandatory in that case.
                request.headers.get("origin") in {None, "null", cfg.base_url},
                "invalid_request",
                "授权请求来源不匹配",
            )
            with hub.repo.transaction() as tx:
                user = principal(tx, user_id)
                pending = tx["oauth_requests"].get(form.get("request_id"))
                require(
                    pending and pending["expires_at"] > hub.timestamp(),
                    "invalid_request",
                    "授权请求过期或已经使用",
                )
                require(form.get("decision") in {"approve", "deny"}, "invalid_request", "授权决定无效")
                parameters = {"state": pending["state"], "iss": cfg.base_url}
                if form["decision"] == "deny":
                    parameters["error"] = "access_denied"
                else:
                    grant_id = uid("grant")
                    tx["oauth_grants"][grant_id] = {
                        "grant_id": grant_id,
                        "user_id": user_id,
                        "client_id": pending["client_id"],
                        "scope": pending["scope"],
                        "epoch": user["auth_epoch"],
                        "revoked": False,
                        "created_at": now(),
                    }
                    code = secrets.token_urlsafe(32)
                    tx["oauth_codes"][token_hash(code)] = {
                        **pending,
                        "grant_id": grant_id,
                        "expires_at": hub.timestamp() + 120,
                    }
                    parameters["code"] = code
                tx["oauth_requests"].pop(pending["request_id"])
                tx.audit(user_id, "oauth_consent", pending["client_id"], result=form["decision"])
                redirect = oauth_redirect(pending["redirect_uri"], **parameters)
            return RedirectResponse(redirect, 303, headers={"Cache-Control": "no-store"})
        except HubError as error:
            return oauth_error(error.code, error.message, error.status)

    @router.post("/oauth/token")
    async def token(request: Request):
        try:
            identity.limit("token:" + (request.client.host if request.client else "local"), 120)
            form = await request.form()
            error = None
            with hub.repo.transaction() as tx:
                client_id = form.get("client_id")
                require(client_id in tx["oauth_clients"], "invalid_client", "客户端无效")
                require(not form.get("client_secret"), "invalid_client", "public client 不使用客户端密钥")
                if form.get("grant_type") == "authorization_code":
                    code_key = token_hash(str(form.get("code", "")))
                    code = tx["oauth_codes"].get(code_key)
                    require(
                        code and code["expires_at"] > hub.timestamp() and code["client_id"] == client_id,
                        "invalid_grant",
                        "授权码失效或已使用",
                    )
                    require(
                        form.get("redirect_uri") == code["redirect_uri"]
                        and form.get("resource") == code["resource"],
                        "invalid_grant",
                        "回调或资源与授权请求不一致",
                    )
                    verifier = form.get("code_verifier", "")
                    require(
                        re.fullmatch(r"[A-Za-z0-9._~-]{43,128}", verifier),
                        "invalid_grant",
                        "PKCE verifier 无效",
                    )
                    challenge = (
                        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
                        .rstrip(b"=")
                        .decode()
                    )
                    require(
                        hmac.compare_digest(challenge, code["code_challenge"]), "invalid_grant", "PKCE 不匹配"
                    )
                    grant = tx["oauth_grants"][code["grant_id"]]
                    tx["oauth_codes"].pop(code_key)
                elif form.get("grant_type") == "refresh_token":
                    key = token_hash(str(form.get("refresh_token", "")))
                    record = tx["oauth_refresh"].get(key)
                    require(
                        record and record["expires_at"] > hub.timestamp(), "invalid_grant", "刷新凭据失效"
                    )
                    grant = tx["oauth_grants"][record["grant_id"]]
                    require(
                        grant["client_id"] == client_id
                        and form.get("resource", cfg.resource) == cfg.resource,
                        "invalid_grant",
                        "客户端或资源不匹配",
                    )
                    if record["used"]:
                        grant["revoked"] = True
                        error = ("invalid_grant", "刷新凭据重用，授权已撤销")
                    record["used"] = True
                else:
                    return oauth_error("unsupported_grant_type", "不支持该授权类型")
                if not error:
                    user = principal(tx, grant["user_id"])
                    require(
                        not grant["revoked"] and grant["epoch"] == user["auth_epoch"],
                        "invalid_grant",
                        "授权已撤销",
                    )
                    payload = identity.issue_tokens(tx, grant)
                tx.audit(
                    grant["user_id"],
                    "oauth_token_exchange",
                    grant["client_id"],
                    result=error[0] if error else "success",
                )
            if error:
                return oauth_error(*error)
            return JSONResponse(payload, headers={"Cache-Control": "no-store", "Pragma": "no-cache"})
        except HubError as error:
            return oauth_error(
                error.code if error.code.islower() else "invalid_grant",
                error.message,
                429 if error.status == 429 else 400,
            )

    @router.post("/oauth/revoke")
    async def revoke(request: Request):
        form = await request.form()
        grant_id = None
        try:
            grant_id = identity.validate_access(str(form.get("token", "")))["grant_id"]
        except HubError:
            pass
        with hub.repo.transaction() as tx:
            record = tx["oauth_refresh"].get(token_hash(str(form.get("token", ""))))
            selected = record["grant_id"] if record else grant_id
            if selected and selected in tx["oauth_grants"]:
                grant = tx["oauth_grants"][selected]
                if grant["client_id"] == form.get("client_id"):
                    grant["revoked"] = True
                    tx.audit(grant["user_id"], "oauth_token_revoke", grant["client_id"])
        return JSONResponse({}, headers={"Cache-Control": "no-store"})

    return router

import re

from backend.app.errors import require
from backend.app.services.authorization import admin, public_user
from backend.app.storage.repository import now, uid


class Organization:
    def action_admin_users(self, tx, user):
        require(admin(user))
        return [public_user(u) for u in tx["users"].values()]

    def validate_roles(self, roles):
        require(
            isinstance(roles, list)
            and roles
            and set(roles) <= {"Member", "SkillAuthor", "Reviewer", "PlatformAdmin"},
            "INVALID_INPUT",
            "平台角色无效",
            422,
        )

    def password_hash(self, password):
        require(10 <= len(password) <= 128, "INVALID_INPUT", "密码长度须为 10～128 字符", 422)
        from backend.app.auth.identity import PASSWORDS

        return PASSWORDS.hash(password)

    def action_create_user(self, tx, user, username, display_name, password, roles=None):
        require(admin(user))
        roles = roles or ["Member", "SkillAuthor"]
        self.validate_roles(roles)
        require(
            re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{2,39}", username)
            and not any(u["username"].casefold() == username.casefold() for u in tx["users"].values()),
            "INVALID_INPUT",
            "账号名称无效或不可用",
            422,
        )
        require(0 < len(display_name.strip()) <= 80, "INVALID_INPUT", "显示姓名无效", 422)
        user_id = uid("user")
        item = {
            "user_id": user_id,
            "username": username,
            "display_name": display_name,
            "password_hash": self.password_hash(password),
            "roles": roles,
            "disabled": False,
            "auth_epoch": 0,
            "created_at": now(),
            "updated_at": now(),
            "revision": 1,
        }
        tx["users"][user_id] = item
        return public_user(item)

    def revoke_user_credentials(self, tx, user_id):
        for ticket in tx["tickets"].values():
            if ticket["user_id"] == user_id:
                ticket["used"] = True
        for session in tx["sessions"].values():
            if session["user_id"] == user_id:
                session["revoked"] = True
        for grant in tx["oauth_grants"].values():
            if grant["user_id"] == user_id:
                grant["revoked"] = True
        tx["users"][user_id]["auth_epoch"] += 1

    def action_edit_user(self, tx, user, user_id, revision, display_name=None, disabled=None, roles=None):
        require(admin(user))
        target = tx["users"].get(user_id)
        require(target, "USER_NOT_FOUND", "账号不存在", 404)
        require(target["revision"] == revision, "REVISION_CONFLICT", "账号已更新，请刷新", 409)
        new_roles = roles if roles is not None else target["roles"]
        self.validate_roles(new_roles)
        new_disabled = target["disabled"] if disabled is None else disabled
        if admin(target) and (new_disabled or "PlatformAdmin" not in new_roles):
            require(
                any(u["user_id"] != user_id and admin(u) and not u["disabled"] for u in tx["users"].values()),
                "LAST_ADMIN",
                "不能移除最后一个有效平台管理员",
                409,
            )
        if display_name is not None:
            require(0 < len(display_name.strip()) <= 80, "INVALID_INPUT", "显示姓名无效", 422)
            target["display_name"] = display_name
        target.update(disabled=new_disabled, roles=new_roles, revision=revision + 1, updated_at=now())
        if new_disabled:
            self.revoke_user_credentials(tx, user_id)
        return public_user(target)

    def action_reset_password(self, tx, user, user_id, password):
        require(admin(user))
        target = tx["users"].get(user_id)
        require(target, "USER_NOT_FOUND", "账号不存在", 404)
        target.update(
            password_hash=self.password_hash(password), revision=target["revision"] + 1, updated_at=now()
        )
        self.revoke_user_credentials(tx, user_id)
        return {"user_id": user_id, "credentials_revoked": True}

    def action_admin_teams(self, tx, user):
        require(admin(user))
        return [
            {**team, "members": [m for m in tx["memberships"].values() if m["team_id"] == team["team_id"]]}
            for team in tx["teams"].values()
        ]

    def action_create_team(self, tx, user, name, owner_user_id, description=""):
        require(admin(user))
        require(
            owner_user_id in tx["users"] and not tx["users"][owner_user_id]["disabled"],
            "INVALID_INPUT",
            "负责人不可用",
            422,
        )
        require(
            0 < len(name.strip()) <= 80 and len(description) <= 1000, "INVALID_INPUT", "团队信息无效", 422
        )
        team_id = uid("team")
        team = {
            "team_id": team_id,
            "name": name,
            "description": description,
            "owner_user_id": owner_user_id,
            "archived": False,
            "created_at": now(),
            "updated_at": now(),
            "revision": 1,
        }
        tx["teams"][team_id] = team
        self.action_set_membership(tx, user, team_id, owner_user_id, "owner", "active")
        return team

    def action_edit_team(self, tx, user, team_id, revision, name=None, archived=None, description=None):
        require(admin(user))
        team = tx["teams"].get(team_id)
        require(team, "TEAM_NOT_FOUND", "团队不存在", 404)
        require(team["revision"] == revision, "REVISION_CONFLICT", "团队已更新，请刷新", 409)
        if name is not None:
            require(0 < len(name.strip()) <= 80, "INVALID_INPUT", "名称无效", 422)
            team["name"] = name
        if description is not None:
            require(len(description) <= 1000, "INVALID_INPUT", "描述过长", 422)
            team["description"] = description
        if archived is not None:
            team["archived"] = archived
        team.update(revision=revision + 1, updated_at=now())
        return team

    def action_set_membership(self, tx, user, team_id, user_id, role="member", status="active"):
        require(admin(user))
        require(team_id in tx["teams"] and user_id in tx["users"], "INVALID_INPUT", "用户或团队不可用", 422)
        require(not tx["teams"][team_id]["archived"], "TEAM_ARCHIVED", "团队已归档，不能调整成员", 409)
        require(
            role in {"member", "owner"} and status in {"active", "removed"},
            "INVALID_INPUT",
            "团队角色或状态无效",
            422,
        )
        key = f"{team_id}:{user_id}"
        previous = tx["memberships"].get(key)
        if previous and previous["role"] == "owner" and (role != "owner" or status != "active"):
            require(
                any(
                    m["team_id"] == team_id
                    and m["user_id"] != user_id
                    and m["role"] == "owner"
                    and m["status"] == "active"
                    for m in tx["memberships"].values()
                ),
                "LAST_TEAM_OWNER",
                "请先指定其他团队负责人",
                409,
            )
        item = {
            "membership_id": key,
            "team_id": team_id,
            "user_id": user_id,
            "role": role,
            "status": status,
            "created_at": previous["created_at"] if previous else now(),
            "updated_at": now(),
        }
        tx["memberships"][key] = item
        if role == "owner" and status == "active":
            tx["teams"][team_id]["owner_user_id"] = user_id
        return item

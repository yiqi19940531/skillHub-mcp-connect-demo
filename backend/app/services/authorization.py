from backend.app.errors import require, missing


def principal(tx, user_id):
    user = tx["users"].get(user_id)
    require(user and not user.get("disabled"), "UNAUTHENTICATED", "请重新登录或授权", 401)
    return user


def admin(user):
    return "PlatformAdmin" in user["roles"]


def reviewer(user):
    return admin(user) or "Reviewer" in user["roles"]


def membership(tx, user_id, team_id):
    return next(
        (
            m
            for m in tx["memberships"].values()
            if m["user_id"] == user_id and m["team_id"] == team_id and m["status"] == "active"
        ),
        None,
    )


def team_owner(tx, user, team_id):
    member = membership(tx, user["user_id"], team_id)
    return admin(user) or bool(member and member["role"] == "owner")


def writable_team(tx, user, team_id):
    team = tx["teams"].get(team_id)
    require(
        team and not team.get("archived") and (admin(user) or membership(tx, user["user_id"], team_id)),
        "FORBIDDEN",
        "团队不可用或没有该团队的创建权限",
        403,
    )
    return team


def acl_visible(tx, user, skill):
    if admin(user) or skill["owner_user_id"] == user["user_id"]:
        return True
    visibility = skill["visibility"]
    if visibility == "enterprise":
        return True
    if visibility == "team":
        return bool(membership(tx, user["user_id"], skill["owner_team_id"]))
    if visibility == "custom":
        return any(
            (grant["type"] == "user" and grant["id"] == user["user_id"])
            or (grant["type"] == "team" and membership(tx, user["user_id"], grant["id"]))
            for grant in skill.get("acl", [])
        )
    return False


def editable(user, skill):
    return admin(user) or skill["owner_user_id"] == user["user_id"]


def readable(tx, user, skill, version):
    if editable(user, skill):
        return True
    if reviewer(user) and version["status"] == "pending_review":
        return True
    return version["status"] in {"published", "deprecated"} and acl_visible(tx, user, skill)


def get_skill(tx, user, skill_id):
    skill = tx["skills"].get(skill_id)
    if not skill or not (
        acl_visible(tx, user, skill)
        or (
            reviewer(user)
            and any(
                v["skill_id"] == skill_id and v["status"] == "pending_review" for v in tx["versions"].values()
            )
        )
    ):
        missing()
    if not editable(user, skill) and not any(
        v["skill_id"] == skill_id and readable(tx, user, skill, v) for v in tx["versions"].values()
    ):
        missing()
    return skill


def get_version(tx, user, skill_id, version=None, install=False):
    skill = get_skill(tx, user, skill_id)
    chosen = version or skill.get("current_version")
    item = tx["versions"].get(f"{skill_id}@{chosen}")
    if not item or not readable(tx, user, skill, item):
        missing()
    if install:
        require(
            item["status"] == "published" and acl_visible(tx, user, skill),
            "VERSION_NOT_PUBLISHED",
            "仅可下载或安装获授权的已发布版本",
            409,
        )
    return skill, item


def public_user(user):
    return {key: value for key, value in user.items() if key not in {"password_hash", "auth_epoch"}}

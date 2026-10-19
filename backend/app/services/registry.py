import re
import json


from backend.app.errors import require
from backend.app.security.packages import digest, SEMVER, safe_path
from backend.app.services.authorization import (
    acl_visible,
    admin,
    editable,
    get_skill,
    get_version,
    membership,
    readable,
    writable_team,
)
from backend.app.storage.repository import now


def version_key(value):
    match = SEMVER.fullmatch(value)
    require(match is not None, "INVALID_INPUT", "版本格式无效", 422)
    prerelease = match[4]
    identifiers = (
        tuple((0, int(part)) if part.isdigit() else (1, part) for part in prerelease.split("."))
        if prerelease
        else ()
    )
    return (int(match[1]), int(match[2]), int(match[3]), 0 if prerelease else 1, identifiers)


class Registry:
    def skill_data(self, tx, user, skill):
        item = {k: v for k, v in skill.items() if k != "acl" or editable(user, skill)}
        item["team_name"] = tx["teams"][skill["owner_team_id"]]["name"]
        item["author_name"] = tx["users"][skill["owner_user_id"]]["display_name"]
        item["favorite"] = f"{user['user_id']}:{skill['skill_id']}" in tx["favorites"]
        item["can_edit"] = editable(user, skill)
        item["allowed_actions"] = ["read", "favorite"] + (["edit", "share"] if item["can_edit"] else [])
        current = tx["versions"].get(f"{skill['skill_id']}@{skill.get('current_version')}")
        item["risk"] = current["risk"] if current else None
        if current and current["status"] == "published" and acl_visible(tx, user, skill):
            item["allowed_actions"] += ["download", "install"]
        ratings = [
            r["score"]
            for r in tx["ratings"].values()
            if r["skill_id"] == skill["skill_id"] and r["version"] == skill.get("current_version")
        ]
        item["rating"] = round(sum(ratings) / len(ratings), 1) if ratings else None
        item["rating_count"] = len(ratings)
        item["favorite_count"] = sum(f["skill_id"] == skill["skill_id"] for f in tx["favorites"].values())
        return item

    def action_whoami(self, tx, user):
        return {
            **{k: user[k] for k in ["user_id", "username", "display_name", "roles"]},
            "teams": self.action_list_my_teams(tx, user),
        }

    def action_list_my_teams(self, tx, user):
        result = []
        for team in tx["teams"].values():
            member = membership(tx, user["user_id"], team["team_id"])
            if admin(user) or member:
                result.append({**team, "membership_role": "admin" if admin(user) else member["role"]})
        return result

    def visible_skills(self, tx, user):
        return [
            s
            for s in tx["skills"].values()
            if s.get("current_version")
            and tx["versions"].get(f"{s['skill_id']}@{s['current_version']}", {}).get("status") == "published"
            and acl_visible(tx, user, s)
        ]

    def action_list_skill_categories(self, tx, user):
        visible = self.visible_skills(tx, user)
        return [
            {**category, "count": sum(s["category_id"] == category["category_id"] for s in visible)}
            for category in tx["categories"].values()
        ]

    def action_list_skills(
        self, tx, user, category=None, team_id=None, cursor=None, limit=30, query="", tags=None, sort="recent"
    ):
        require(sort in {"recent", "popular", "relevance"}, "INVALID_INPUT", "不支持的排序", 422)
        require(isinstance(limit, int) and 1 <= limit <= 100, "INVALID_INPUT", "limit 应为 1～100", 422)
        words = query.casefold().split()
        rows = []
        for skill in self.visible_skills(tx, user):
            if category and skill["category_id"] != category:
                continue
            if team_id and skill["owner_team_id"] != team_id:
                continue
            if tags and not set(tags).issubset(skill["tags"]):
                continue
            title = f"{skill['name']} {skill['display_name']}".casefold()
            tag_text = " ".join(skill["tags"]).casefold()
            description = skill["description"].casefold()
            if not all(word in title + " " + tag_text + " " + description for word in words):
                continue
            score = sum(5 * (w in title) + 3 * (w in tag_text) + (w in description) for w in words)
            rows.append((score, self.skill_data(tx, user, skill)))
        rows.sort(key=lambda row: row[1]["skill_id"])
        if sort == "popular":
            rows.sort(key=lambda row: row[1]["favorite_count"], reverse=True)
        elif sort == "relevance" or words:
            rows.sort(key=lambda row: row[0], reverse=True)
        else:
            rows.sort(key=lambda row: row[1].get("published_at", row[1]["created_at"]), reverse=True)
        require(cursor is None or re.fullmatch(r"\d{1,8}", cursor), "INVALID_INPUT", "分页游标无效", 422)
        offset = int(cursor or 0)
        return {
            "items": [row[1] for row in rows[offset : offset + limit]],
            "total": len(rows),
            "next_cursor": str(offset + limit) if offset + limit < len(rows) else None,
        }

    def action_search_skills(
        self, tx, user, query, category=None, tags=None, team_id=None, cursor=None, limit=30
    ):
        return self.action_list_skills(tx, user, category, team_id, cursor, limit, query, tags, "relevance")

    def action_get_skill(self, tx, user, skill_id):
        skill = get_skill(tx, user, skill_id)
        return {
            **self.skill_data(tx, user, skill),
            "versions": self.action_list_skill_versions(tx, user, skill_id),
        }

    def version_data(self, version):
        return {key: value for key, value in version.items() if key not in {"bundle_path", "expanded_path"}}

    def action_list_skill_versions(self, tx, user, skill_id):
        skill = get_skill(tx, user, skill_id)
        return [
            self.version_data(v)
            for v in sorted(tx["versions"].values(), key=lambda v: version_key(v["version"]), reverse=True)
            if v["skill_id"] == skill_id and readable(tx, user, skill, v)
        ]

    def action_get_skill_instructions(self, tx, user, skill_id, version=None):
        _, item = get_version(tx, user, skill_id, version)
        return self.action_get_skill_file(tx, user, skill_id, item["version"], "SKILL.md")

    def action_get_skill_file(self, tx, user, skill_id, version, relative_path):
        _, item = get_version(tx, user, skill_id, version)
        safe_path(relative_path)
        entry = next((f for f in item["manifest"] if f["path"] == relative_path), None)
        require(entry is not None, "FILE_NOT_FOUND", "文件不存在", 404)
        require(
            not entry["binary"] and entry["size"] <= 65536,
            "FILE_REQUIRES_DOWNLOAD",
            "请通过受控 ZIP 下载获取此文件",
            413,
        )
        content = (self.settings.data_dir / item["expanded_path"] / relative_path).read_bytes()
        require(digest(content) == entry["sha256"], "DIGEST_MISMATCH", "服务端文件完整性校验失败", 409)
        return {
            "skill_id": skill_id,
            "version": version,
            "path": relative_path,
            "content": content.decode("utf-8"),
            "sha256": entry["sha256"],
            "trusted_as": "business_content",
        }

    def validate_acl(self, tx, visibility, acl):
        require(visibility in {"private", "team", "enterprise", "custom"}, "INVALID_INPUT", "可见性无效", 422)
        require(isinstance(acl, list) and len(acl) <= 100, "INVALID_INPUT", "ACL 无效", 422)
        clean = []
        for grant in acl:
            require(
                isinstance(grant, dict)
                and set(grant) == {"type", "id"}
                and grant["type"] in {"user", "team"},
                "INVALID_INPUT",
                "ACL 须使用 type/id",
                422,
            )
            require(
                grant["id"] in tx["users" if grant["type"] == "user" else "teams"],
                "INVALID_INPUT",
                "ACL 对象不可用",
                422,
            )
            if grant not in clean:
                clean.append(grant)
        require(visibility != "custom" or clean, "INVALID_INPUT", "自定义可见性须指定授权对象", 422)
        require(visibility == "custom" or not clean, "INVALID_INPUT", "仅 custom 可见性使用 ACL", 422)
        return clean

    def action_upload_skill(
        self,
        tx,
        user,
        team_id,
        visibility="team",
        skill_md=None,
        upload_id=None,
        version="0.1.0",
        skill_id=None,
        display_name=None,
        category_id=None,
        tags=None,
        acl=None,
    ):
        writable_team(tx, user, team_id)
        require(
            bool(skill_md is not None) != bool(upload_id),
            "UPLOAD_INVALID",
            "须且只能提供 skill_md 或 upload_id",
            400,
        )
        require(
            isinstance(version, str) and len(version) <= 64 and SEMVER.fullmatch(version),
            "UPLOAD_INVALID",
            "版本须为 SemVer，例如 1.0.0",
            400,
        )
        if skill_md is not None:
            require(
                len(skill_md.encode()) <= 65536,
                "UPLOAD_INVALID",
                "文本上传最长 64 KiB；更大内容请使用 ZIP",
                413,
            )
            files = {"SKILL.md": skill_md.encode()}
        else:
            submission_fingerprint = digest(
                json.dumps(
                    {
                        "team_id": team_id,
                        "visibility": visibility,
                        "version": version,
                        "skill_id": skill_id,
                        "display_name": display_name,
                        "category_id": category_id,
                        "tags": tags,
                        "acl": acl,
                    },
                    sort_keys=True,
                    ensure_ascii=False,
                ).encode()
            )
            upload = tx["uploads"].get(upload_id)
            require(
                upload and upload["user_id"] == user["user_id"] and upload["team_id"] == team_id,
                "UPLOAD_INVALID",
                "上传会话不可用",
                400,
            )
            if upload.get("submitted"):
                require(
                    upload.get("submitted_fingerprint") == submission_fingerprint,
                    "IDEMPOTENCY_CONFLICT",
                    "此上传会话已用于其他提交，请创建新会话",
                    409,
                )
                require(editable(user, get_skill(tx, user, upload["submitted"])))
                return upload["submitted_result"]
            require(
                upload.get("status") == "received" and upload["expires_at"] > self.timestamp(),
                "UPLOAD_EXPIRED",
                "上传会话未完成或已过期",
                410,
            )
            raw = (self.settings.data_dir / upload["path"]).read_bytes()
            require(digest(raw) == upload["sha256"], "DIGEST_MISMATCH", "上传包摘要不一致", 409)
            files = self.packages.unpack(raw)
        frontmatter, _ = self.packages.validate(files)
        name = frontmatter["name"]
        existing = next((s for s in tx["skills"].values() if s["name"] == name), None)
        if skill_id:
            skill = get_skill(tx, user, skill_id)
            require(
                editable(user, skill) and skill["owner_team_id"] == team_id,
                "FORBIDDEN",
                "不能维护此 Skill 或改变所属团队",
                403,
            )
            require(skill["name"] == name, "UPLOAD_INVALID", "更新不能改变 Skill name", 400)
        else:
            require(
                existing is None, "NAME_UNAVAILABLE", "该名称不可用；更新已有 Skill 时请指定获授权的 ID", 409
            )
            skill_id = name
            skill = {
                "skill_id": skill_id,
                "name": name,
                "owner_user_id": user["user_id"],
                "owner_team_id": team_id,
                "current_version": None,
                "created_at": now(),
                "revision": 0,
            }
        version_id = f"{skill_id}@{version}"
        previous = tx["versions"].get(version_id)
        require(
            not previous or previous["status"] in {"draft", "rejected"},
            "VERSION_IMMUTABLE",
            "待审核或已发布版本不能覆盖，请创建新版本",
            409,
        )
        category_id = category_id or skill.get("category_id", "ai-coding")
        require(category_id in tx["categories"], "INVALID_INPUT", "分类不可用", 422)
        tags = tags if tags is not None else skill.get("tags", [])
        require(
            len(tags) <= 20 and all(isinstance(tag, str) and 0 < len(tag) <= 40 for tag in tags),
            "INVALID_INPUT",
            "标签最多 20 个，每个最长 40 字符",
            422,
        )
        label = display_name or skill.get("display_name") or name
        require(0 < len(label.strip()) <= 100, "INVALID_INPUT", "显示名称最长 100 字符", 422)
        metadata = {
            "display_name": label,
            "description": frontmatter["description"],
            "category_id": category_id,
            "tags": list(dict.fromkeys(tags)),
            "visibility": visibility,
            "acl": self.validate_acl(tx, visibility, acl or []),
        }
        stored = self.packages.save(files, skill_id, version)
        item = {
            **stored,
            "skill_id": skill_id,
            "version": version,
            "status": "draft",
            "proposed_metadata": metadata,
            "submitted_by": user["user_id"],
            "created_at": previous["created_at"] if previous else now(),
            "updated_at": now(),
            "revision": (previous or {}).get("revision", 0) + 1,
            "review_id": None,
        }
        tx["versions"][version_id] = item
        if not skill.get("current_version"):
            skill.update(metadata)
        skill.update(updated_at=now(), revision=skill["revision"] + 1)
        tx["skills"][skill_id] = skill
        result = {
            "skill": self.skill_data(tx, user, skill),
            "version": self.version_data(item),
            "status": "draft",
        }
        if upload_id:
            tx["uploads"][upload_id].update(
                submitted=skill_id, submitted_fingerprint=submission_fingerprint, submitted_result=result
            )
        return result

    def action_list_my_uploads(self, tx, user):
        return [
            {
                **self.skill_data(tx, user, s),
                "versions": self.action_list_skill_versions(tx, user, s["skill_id"]),
            }
            for s in tx["skills"].values()
            if s["owner_user_id"] == user["user_id"]
        ]

    def action_edit_skill(self, tx, user, skill_id, revision, **changes):
        skill = get_skill(tx, user, skill_id)
        require(editable(user, skill))
        writable_team(tx, user, skill["owner_team_id"])
        require(skill["revision"] == revision, "REVISION_CONFLICT", "内容已更新，请刷新后重试", 409)
        require(
            set(changes) <= {"display_name", "category_id", "tags"},
            "INVALID_INPUT",
            "只能修改显示名称、分类和标签",
            422,
        )
        if "category_id" in changes:
            require(changes["category_id"] in tx["categories"], "INVALID_INPUT", "分类不可用", 422)
        if "display_name" in changes:
            require(0 < len(changes["display_name"].strip()) <= 100, "INVALID_INPUT", "显示名称无效", 422)
        if "tags" in changes:
            require(
                len(changes["tags"]) <= 20
                and all(isinstance(t, str) and 0 < len(t) <= 40 for t in changes["tags"]),
                "INVALID_INPUT",
                "标签无效",
                422,
            )
        skill.update(changes, revision=revision + 1, updated_at=now())
        return self.skill_data(tx, user, skill)

    def action_set_version_status(self, tx, user, skill_id, version, status):
        skill, item = get_version(tx, user, skill_id, version)
        require(editable(user, skill))
        require(
            status in {"deprecated", "revoked"} and item["status"] in {"published", "deprecated"},
            "INVALID_TRANSITION",
            "只可废弃或撤回已发布版本",
            409,
        )
        item.update(status=status, updated_at=now(), revision=item["revision"] + 1)
        published = [
            v["version"]
            for v in tx["versions"].values()
            if v["skill_id"] == skill_id and v["status"] == "published"
        ]
        skill.update(
            current_version=max(published, key=version_key) if published else None,
            revision=skill["revision"] + 1,
            updated_at=now(),
        )
        return self.version_data(item)

    def action_rate_skill(self, tx, user, skill_id, version, score):
        get_version(tx, user, skill_id, version, install=True)
        require(
            isinstance(score, int) and not isinstance(score, bool) and 1 <= score <= 5,
            "INVALID_INPUT",
            "评分应为 1～5 的整数",
            422,
        )
        key = f"{user['user_id']}:{skill_id}@{version}"
        tx["ratings"][key] = {
            "user_id": user["user_id"],
            "skill_id": skill_id,
            "version": version,
            "score": score,
            "updated_at": now(),
        }
        return tx["ratings"][key]

    def action_recommend_skills(self, tx, user, query="", tags=None, limit=6):
        result = self.action_list_skills(tx, user, query=query, tags=tags, sort="relevance", limit=limit)
        return [
            {**item, "recommendation_reason": "名称、标签或描述匹配" if query or tags else "当前可访问的技能"}
            for item in result["items"]
        ]

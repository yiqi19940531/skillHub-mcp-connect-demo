from backend.app.errors import require
from backend.app.security.packages import SECRET, digest
from backend.app.services.authorization import (
    acl_visible,
    admin,
    editable,
    get_skill,
    get_version,
    membership,
    reviewer,
    team_owner,
    writable_team,
)
from backend.app.services.registry import version_key
from backend.app.storage.repository import now, uid


class Governance:
    def action_list_favorites(self, tx, user):
        return [
            self.skill_data(tx, user, s)
            for s in self.visible_skills(tx, user)
            if f"{user['user_id']}:{s['skill_id']}" in tx["favorites"]
        ]

    def action_add_favorite(self, tx, user, skill_id):
        get_version(tx, user, skill_id, install=True)
        key = f"{user['user_id']}:{skill_id}"
        tx["favorites"].setdefault(
            key, {"user_id": user["user_id"], "skill_id": skill_id, "created_at": now()}
        )
        return {"skill_id": skill_id, "favorite": True}

    def action_remove_favorite(self, tx, user, skill_id):
        tx["favorites"].pop(f"{user['user_id']}:{skill_id}", None)
        return {"skill_id": skill_id, "favorite": False}

    def collection_visible(self, tx, user, collection):
        return (
            admin(user)
            or membership(tx, user["user_id"], collection["owner_team_id"])
            or any(
                (g["type"] == "user" and g["id"] == user["user_id"])
                or (g["type"] == "team" and membership(tx, user["user_id"], g["id"]))
                for g in collection.get("acl", [])
            )
        )

    def get_collection(self, tx, user, collection_id, write=False):
        collection = tx["collections"].get(collection_id)
        require(
            collection and not collection.get("archived") and self.collection_visible(tx, user, collection),
            "COLLECTION_NOT_ACCESSIBLE",
            "收藏集不存在或不可访问",
            404,
        )
        if write:
            writable_team(tx, user, collection["owner_team_id"])
            require(team_owner(tx, user, collection["owner_team_id"]))
        return collection

    def action_list_collections(self, tx, user, team_id=None):
        result = []
        for item in tx["collections"].values():
            if item.get("archived") or (team_id and item["owner_team_id"] != team_id):
                continue
            if not self.collection_visible(tx, user, item):
                continue
            skills = self.action_list_collection_skills(tx, user, item["collection_id"])
            result.append(
                {
                    **{k: v for k, v in item.items() if k != "skill_ids"},
                    "count": len(skills),
                    "can_manage": bool(team_owner(tx, user, item["owner_team_id"])),
                }
            )
        return result

    def action_list_collection_skills(self, tx, user, collection_id):
        item = self.get_collection(tx, user, collection_id)
        return [
            self.skill_data(tx, user, s)
            for s in self.visible_skills(tx, user)
            if s["skill_id"] in item["skill_ids"]
        ]

    def action_create_collection(self, tx, user, team_id, name, acl=None):
        writable_team(tx, user, team_id)
        require(team_owner(tx, user, team_id))
        require(0 < len(name.strip()) <= 100, "INVALID_INPUT", "收藏集名称最长 100 字符", 422)
        grants = self.validate_acl(tx, "custom", acl) if acl else []
        collection_id = uid("col")
        item = {
            "collection_id": collection_id,
            "name": name,
            "owner_team_id": team_id,
            "acl": grants,
            "skill_ids": [],
            "archived": False,
            "created_at": now(),
            "updated_at": now(),
            "revision": 1,
        }
        tx["collections"][collection_id] = item
        return item

    def action_edit_collection(self, tx, user, collection_id, revision, name=None, archived=False):
        item = self.get_collection(tx, user, collection_id, write=True)
        require(item["revision"] == revision, "REVISION_CONFLICT", "收藏集已更新，请刷新", 409)
        if name is not None:
            require(0 < len(name.strip()) <= 100, "INVALID_INPUT", "名称无效", 422)
            item["name"] = name
        item.update(archived=archived, revision=revision + 1, updated_at=now())
        return item

    def action_add_skill_to_collection(self, tx, user, collection_id, skill_id):
        collection = self.get_collection(tx, user, collection_id, write=True)
        skill, _ = get_version(tx, user, skill_id, install=True)
        for member in tx["users"].values():
            if not member["disabled"] and self.collection_visible(tx, member, collection):
                require(
                    acl_visible(tx, member, skill),
                    "COLLECTION_ACL_MISMATCH",
                    "收藏集受众没有完整的 Skill 访问权限",
                    409,
                )
        if skill_id not in collection["skill_ids"]:
            collection["skill_ids"].append(skill_id)
            collection.update(revision=collection["revision"] + 1, updated_at=now())
        return {"collection_id": collection_id, "skill_id": skill_id, "added": True}

    def action_remove_skill_from_collection(self, tx, user, collection_id, skill_id):
        collection = self.get_collection(tx, user, collection_id, write=True)
        collection["skill_ids"] = [s for s in collection["skill_ids"] if s != skill_id]
        collection.update(revision=collection["revision"] + 1, updated_at=now())
        return {"collection_id": collection_id, "skill_id": skill_id, "removed": True}

    def action_request_skill_review(self, tx, user, skill_id, version):
        skill, item = get_version(tx, user, skill_id, version)
        require(editable(user, skill))
        writable_team(tx, user, skill["owner_team_id"])
        if item["status"] == "pending_review":
            return tx["reviews"][item["review_id"]]
        require(
            item["status"] in {"draft", "rejected"}, "INVALID_TRANSITION", "只有草稿或驳回版本可以送审", 409
        )
        review_id = uid("review")
        item.update(
            status="pending_review", review_id=review_id, revision=item["revision"] + 1, updated_at=now()
        )
        record = {
            "review_id": review_id,
            "kind": "content",
            "skill_id": skill_id,
            "version": version,
            "submitted_by": user["user_id"],
            "reviewed_by": None,
            "decision": "pending",
            "reason": "",
            "sha256": item["sha256"],
            "version_revision": item["revision"],
            "created_at": now(),
            "updated_at": now(),
        }
        tx["reviews"][review_id] = record
        return record

    def can_read_review(self, tx, user, record):
        skill = tx["skills"].get(record["skill_id"])
        return bool(
            skill
            and (
                reviewer(user)
                or record["submitted_by"] == user["user_id"]
                or skill["owner_user_id"] == user["user_id"]
                or (record["kind"] == "share" and team_owner(tx, user, skill["owner_team_id"]))
            )
        )

    def review_data(self, tx, user, record):
        skill = tx["skills"][record["skill_id"]]
        item = tx["versions"].get(f"{record['skill_id']}@{record.get('version')}")
        result = {
            **record,
            "skill_name": skill["display_name"],
            "owner_team_id": skill["owner_team_id"],
            "submitter_name": tx["users"][record["submitted_by"]]["display_name"],
            "can_decide": self.can_decide_review(tx, user, record),
        }
        if item:
            result["version_detail"] = self.version_data(item)
            content = (self.settings.data_dir / item["expanded_path"] / "SKILL.md").read_bytes()
            result["instructions"] = content[:65536].decode("utf-8", errors="replace")
        return result

    def can_decide_review(self, tx, user, record):
        skill = tx["skills"][record["skill_id"]]
        if user["user_id"] in {record["submitted_by"], skill["owner_user_id"]}:
            return False
        if record["kind"] == "content":
            item = tx["versions"][f"{record['skill_id']}@{record['version']}"]
            if item["submitted_by"] == user["user_id"]:
                return False
            return bool(
                reviewer(user) and (item["proposed_metadata"]["visibility"] != "enterprise" or admin(user))
            )
        request = tx["share_requests"][record["share_request_id"]]
        return admin(user) or (
            request["visibility"] != "enterprise" and team_owner(tx, user, skill["owner_team_id"])
        )

    def action_get_skill_review_status(self, tx, user, review_id):
        record = tx["reviews"].get(review_id)
        require(
            record and self.can_read_review(tx, user, record),
            "REVIEW_NOT_ACCESSIBLE",
            "审核记录不可访问",
            404,
        )
        return self.review_data(tx, user, record)

    def action_list_reviews(self, tx, user):
        return [
            self.review_data(tx, user, r)
            for r in reversed(list(tx["reviews"].values()))
            if self.can_read_review(tx, user, r)
        ]

    def action_decide_review(self, tx, user, review_id, decision, reason=""):
        record = tx["reviews"].get(review_id)
        require(
            record and self.can_read_review(tx, user, record),
            "REVIEW_NOT_ACCESSIBLE",
            "审核记录不可访问",
            404,
        )
        require(
            self.can_decide_review(tx, user, record), "FORBIDDEN", "无审核权限，或正在审批自己的申请", 403
        )
        require(record["decision"] == "pending", "INVALID_TRANSITION", "该审核已经处理", 409)
        require(
            decision in {"approved", "rejected"}
            and len(reason) <= 2000
            and (decision != "rejected" or reason.strip()),
            "INVALID_INPUT",
            "驳回须填写原因",
            422,
        )
        skill = tx["skills"][record["skill_id"]]
        require(not tx["teams"][skill["owner_team_id"]].get("archived"), "TEAM_ARCHIVED", "团队已归档", 409)
        if record["kind"] == "content":
            item = tx["versions"][f"{record['skill_id']}@{record['version']}"]
            require(
                item["status"] == "pending_review"
                and item["sha256"] == record["sha256"]
                and item["revision"] == record["version_revision"],
                "REVISION_CONFLICT",
                "送审内容已变化",
                409,
            )
            if decision == "approved":
                bundle = (self.settings.data_dir / item["bundle_path"]).read_bytes()
                require(digest(bundle) == item["sha256"], "DIGEST_MISMATCH", "送审归档完整性校验失败", 409)
                files = {}
                for entry in item["manifest"]:
                    content = (self.settings.data_dir / item["expanded_path"] / entry["path"]).read_bytes()
                    require(
                        digest(content) == entry["sha256"], "DIGEST_MISMATCH", "送审文件完整性校验失败", 409
                    )
                    files[entry["path"]] = content
                self.packages.validate(files)
            item.update(
                status="published" if decision == "approved" else "rejected",
                updated_at=now(),
                revision=item["revision"] + 1,
            )
            if decision == "approved":
                item["published_at"] = now()
                published = [
                    v
                    for v in tx["versions"].values()
                    if v["skill_id"] == skill["skill_id"] and v["status"] == "published"
                ]
                latest = max(published, key=lambda v: version_key(v["version"]))
                # Older approvals must not restore stale ACL/metadata after sharing was revoked.
                if latest["version"] == item["version"]:
                    skill.update(
                        latest["proposed_metadata"],
                        current_version=latest["version"],
                        published_at=latest["published_at"],
                    )
                skill.update(updated_at=now(), revision=skill["revision"] + 1)
        else:
            request = tx["share_requests"][record["share_request_id"]]
            require(
                skill["revision"] == request["skill_revision"],
                "REVISION_CONFLICT",
                "Skill 已变化，请重新发起共享",
                409,
            )
            request.update(status=decision, updated_at=now())
            if decision == "approved":
                skill.update(
                    visibility=request["visibility"],
                    acl=request["acl"],
                    revision=skill["revision"] + 1,
                    updated_at=now(),
                )
        record.update(decision=decision, reason=reason, reviewed_by=user["user_id"], updated_at=now())
        return self.review_data(tx, user, record)

    def action_share_skill(self, tx, user, skill_id, visibility, acl=None):
        skill, item = get_version(tx, user, skill_id, install=True)
        require(editable(user, skill))
        writable_team(tx, user, skill["owner_team_id"])
        grants = self.validate_acl(tx, visibility, acl or [])
        request_id, review_id = uid("share"), uid("review")
        request = {
            "share_request_id": request_id,
            "skill_id": skill_id,
            "visibility": visibility,
            "acl": grants,
            "skill_revision": skill["revision"],
            "status": "pending",
            "submitted_by": user["user_id"],
            "created_at": now(),
            "updated_at": now(),
        }
        tx["share_requests"][request_id] = request
        record = {
            "review_id": review_id,
            "kind": "share",
            "skill_id": skill_id,
            "version": item["version"],
            "submitted_by": user["user_id"],
            "decision": "pending",
            "reviewed_by": None,
            "reason": "",
            "share_request_id": request_id,
            "proposed_visibility": visibility,
            "proposed_acl": grants,
            "created_at": now(),
            "updated_at": now(),
        }
        tx["reviews"][review_id] = record
        return record

    def action_revoke_share(self, tx, user, skill_id, visibility="private", acl=None):
        skill = get_skill(tx, user, skill_id)
        require(editable(user, skill))
        grants = self.validate_acl(tx, visibility, acl or [])
        proposed = {**skill, "visibility": visibility, "acl": grants}
        # A shrink never grants enterprise visibility or introduces a new ACL subject.
        symbolic_shrink = (
            visibility == "private"
            or (skill["visibility"] == "enterprise")
            or (
                visibility == "custom"
                and skill["visibility"] == "custom"
                and all(g in skill["acl"] for g in grants)
            )
        )
        require(
            symbolic_shrink
            and all(
                not acl_visible(tx, u, proposed) or acl_visible(tx, u, skill) for u in tx["users"].values()
            ),
            "APPROVAL_REQUIRED",
            "扩大授权范围须提交共享审批",
            409,
        )
        skill.update(visibility=visibility, acl=grants, revision=skill["revision"] + 1, updated_at=now())
        return self.skill_data(tx, user, skill)

    def action_report_skill_issue(self, tx, user, skill_id, description, kind="description", version=None):
        skill, item = get_version(tx, user, skill_id, version)
        require(
            kind in {"description", "broken", "security", "other"} and 0 < len(description.strip()) <= 4000,
            "INVALID_INPUT",
            "问题类型或描述无效",
            422,
        )
        require(not SECRET.search(description), "INVALID_INPUT", "反馈中不能包含凭据", 422)
        issue_id = uid("issue")
        issue = {
            "issue_id": issue_id,
            "skill_id": skill_id,
            "version": item["version"],
            "kind": kind,
            "description": description,
            "user_id": user["user_id"],
            "status": "open",
            "resolution": "",
            "created_at": now(),
            "updated_at": now(),
            "revision": 1,
        }
        tx["issues"][issue_id] = issue
        return issue

    def action_list_issues(self, tx, user):
        return [
            {
                **issue,
                "can_manage": bool(
                    admin(user) or tx["skills"][issue["skill_id"]]["owner_user_id"] == user["user_id"]
                ),
            }
            for issue in tx["issues"].values()
            if admin(user)
            or issue["user_id"] == user["user_id"]
            or tx["skills"][issue["skill_id"]]["owner_user_id"] == user["user_id"]
        ]

    def action_update_issue(self, tx, user, issue_id, status, revision, resolution=""):
        issue = tx["issues"].get(issue_id)
        require(
            issue and (admin(user) or tx["skills"][issue["skill_id"]]["owner_user_id"] == user["user_id"])
        )
        require(
            status in {"open", "in_progress", "resolved", "closed"} and len(resolution) <= 2000,
            "INVALID_INPUT",
            "问题状态或处理说明无效",
            422,
        )
        require(issue["revision"] == revision, "REVISION_CONFLICT", "反馈已更新，请刷新", 409)
        issue.update(status=status, resolution=resolution, revision=revision + 1, updated_at=now())
        return issue

    def action_share_targets(self, tx, user):
        return {
            "teams": [
                {"id": t["team_id"], "name": t["name"]} for t in tx["teams"].values() if not t["archived"]
            ],
            "users": [
                {"id": u["user_id"], "name": u["display_name"]}
                for u in tx["users"].values()
                if not u["disabled"]
            ],
        }

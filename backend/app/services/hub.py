import hashlib
import json
import time

from backend.app.config import Settings
from backend.app.errors import HubError, require
from backend.app.security.packages import Packages
from backend.app.services.authorization import principal, get_skill, editable, get_version, writable_team
from backend.app.services.registry import Registry
from backend.app.services.governance import Governance
from backend.app.services.transfers import Transfers
from backend.app.services.organization import Organization
from backend.app.services.analytics import Analytics
from backend.app.storage.repository import Repository, now


class Hub(Registry, Governance, Transfers, Organization, Analytics):
    def __init__(self, settings: Settings):
        settings.validate()
        self.settings = settings
        self.repo = Repository(settings.data_dir)
        self.packages = Packages(settings)

    @staticmethod
    def timestamp():
        return int(time.time())

    def run(self, user_id, action, arguments=None, *, channel="service"):
        arguments = dict(arguments or {})
        request_id = arguments.pop("request_id", None)
        require(
            request_id is None
            or (
                action in {"upload_skill", "report_install_result"}
                and isinstance(request_id, str)
                and 0 < len(request_id) <= 128
            ),
            "INVALID_INPUT",
            "该操作不支持此重试标识",
            422,
        )
        method = getattr(self, "action_" + action, None)
        require(callable(method), "UNKNOWN_ACTION", "不支持的操作", 404)
        try:
            with self.repo.transaction() as tx:
                user = principal(tx, user_id)
                cache_key = f"{user_id}:{action}:{request_id}" if request_id else None
                body_hash = hashlib.sha256(
                    json.dumps(arguments, sort_keys=True, ensure_ascii=False).encode()
                ).hexdigest()
                if cache_key and cache_key in tx["idempotency"]:
                    cache = tx["idempotency"][cache_key]
                    require(cache["hash"] == body_hash, "IDEMPOTENCY_CONFLICT", "重试标识已用于其他请求", 409)
                    if action == "upload_skill":
                        skill = get_skill(tx, user, cache["result"]["skill"]["skill_id"])
                        require(editable(user, skill))
                        writable_team(tx, user, skill["owner_team_id"])
                    elif arguments.get("operation", "install") != "uninstall":
                        get_version(tx, user, arguments["skill_id"], arguments["version"], install=True)
                    tx.audit(user_id, action, arguments.get("skill_id"), result="replayed")
                    return cache["result"]
                result = method(tx, user, **arguments)
                self.track_usage(tx, action, arguments, result, channel)
                if cache_key:
                    require(len(request_id) <= 128, "INVALID_INPUT", "重试标识过长", 422)
                    tx["idempotency"][cache_key] = {"hash": body_hash, "result": result, "created_at": now()}
                tx.audit(
                    user_id,
                    action,
                    arguments.get("skill_id")
                    or arguments.get("team_id")
                    or arguments.get("collection_id")
                    or arguments.get("review_id"),
                )
                return result
        except HubError as error:
            with self.repo.transaction() as tx:
                tx.audit(user_id, action, result=error.code, decision="deny")
            raise

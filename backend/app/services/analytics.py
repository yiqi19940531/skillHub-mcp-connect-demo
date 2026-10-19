"""Small platform-side counters; offline Agent execution is not observable here."""

from datetime import datetime, timedelta, timezone

from backend.app.errors import missing, require
from backend.app.storage.repository import now, uid

COUNTERS = ("detail_views", "content_fetches", "downloads", "installations", "discoveries")


class Analytics:
    @staticmethod
    def record_usage(tx, skill_id, kind, *, version=None, source="service", unique_key=None):
        require(kind in COUNTERS, "INVALID_INPUT", "统计事件类型无效", 422)
        key = unique_key or uid("usage")
        if key not in tx["usage_events"]:
            tx["usage_events"][key] = {
                "skill_id": skill_id,
                "kind": kind,
                "version": version,
                "source": source,
                "time": now(),
            }

    def track_usage(self, tx, action, arguments, result, source):
        kind = {
            "get_skill": "detail_views",
            "get_skill_file": "content_fetches",
            "get_skill_instructions": "content_fetches",
        }.get(action)
        if kind:
            self.record_usage(
                tx, arguments["skill_id"], kind, version=arguments.get("version"), source=source
            )
        if action == "report_install_result" and arguments["status"] in {"written", "discovered"}:
            record = result
            self.record_usage(
                tx,
                record["skill_id"],
                "installations",
                version=record["version"],
                source=source,
                unique_key="installation:" + record["installation_id"],
            )
            if arguments["status"] == "discovered":
                self.record_usage(
                    tx,
                    record["skill_id"],
                    "discoveries",
                    version=record["version"],
                    source=source,
                    unique_key="discovery:" + record["installation_id"],
                )

    def action_usage_stats(self, tx, user, days=30, skill_id=None):
        require(
            isinstance(days, int) and not isinstance(days, bool) and 1 <= days <= 365,
            "INVALID_INPUT",
            "统计范围须为 1～365 天",
            422,
        )
        # Both rows and totals use current ACL, including permission revocation.
        visible = {s["skill_id"]: s for s in self.visible_skills(tx, user)}
        if skill_id is not None:
            if skill_id not in visible:
                missing()
            visible = {skill_id: visible[skill_id]}
        rows = {
            sid: {
                "skill_id": sid,
                "display_name": s["display_name"],
                "team_name": tx["teams"][s["owner_team_id"]]["name"],
                **dict.fromkeys(COUNTERS, 0),
                "favorites": 0,
            }
            for sid, s in visible.items()
        }
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        for event in tx["usage_events"].values():
            if event["skill_id"] in rows and datetime.fromisoformat(event["time"]) >= cutoff:
                rows[event["skill_id"]][event["kind"]] += 1
        for favorite in tx["favorites"].values():
            if favorite["skill_id"] in rows:
                rows[favorite["skill_id"]]["favorites"] += 1
        items = sorted(
            rows.values(),
            key=lambda r: (-r["downloads"], -r["installations"], -r["content_fetches"], r["skill_id"]),
        )
        return {
            "period_days": days,
            "from": cutoff.isoformat(),
            "totals": {key: sum(row[key] for row in items) for key in (*COUNTERS, "favorites")},
            "items": items,
            "scope": "currently_authorized_published_skills",
            "measurement": "platform_requests_and_agent_reports",
        }

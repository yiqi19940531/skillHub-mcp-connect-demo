from datetime import datetime, timedelta, timezone

from conftest import api_post, authorize, login, rpc
from backend.app.storage.repository import Repository


def test_platform_metrics_only_count_successful_access_and_redeemed_download(client, app):
    token = authorize(client)["access_token"]
    sid = "java-code-review"
    assert client.get(f"/api/v1/skills/{sid}").status_code == 200
    result = rpc(client, token, "get_skill_instructions", {"skill_id": sid})
    assert not result["isError"]
    plan = api_post(client, "/installations/preflight", {"skill_id": sid, "client": "qoder-ide"})
    assert plan.status_code == 200
    package = api_post(client, f"/skills/{sid}/download", {"version": "1.0.0"}).json()["data"]
    before = client.get(f"/api/v1/skills/{sid}/stats").json()["data"]["totals"]
    assert before["detail_views"] == 1 and before["content_fetches"] == 1
    assert before["downloads"] == before["installations"] == 0
    assert client.get(package["download_url"]).status_code == 200
    assert client.get(package["download_url"]).status_code == 410
    assert client.get(f"/api/v1/skills/{sid}/stats").json()["data"]["totals"]["downloads"] == 1
    # File persistence and event payload contain no credentials, actor IDs or local paths.
    events = Repository(app.state.hub.settings.data_dir).snapshot()["usage_events"]
    assert len(events) == 3
    assert all(set(event) == {"skill_id", "kind", "version", "source", "time"} for event in events.values())
    assert {event["source"] for event in events.values()} == {"web", "mcp", "transfer"}
    login(client, "lisi")
    assert client.get(f"/api/v1/skills/{sid}").status_code == 404
    assert client.get(f"/api/v1/skills/{sid}/stats").status_code == 404
    stats = client.get("/api/v1/analytics").json()["data"]
    assert sid not in {row["skill_id"] for row in stats["items"]}
    assert stats["totals"]["downloads"] == stats["totals"]["detail_views"] == 0


def test_installation_and_discovery_reports_deduplicate_by_installation(client):
    login(client)
    plan = api_post(
        client, "/installations/plan", {"skill_id": "git-commit-guide", "client": "qoder-ide"}
    ).json()["data"]
    body = {
        "skill_id": "git-commit-guide",
        "version": "1.0.0",
        "client": "qoder-ide",
        "scope": "project",
        "installation_id": plan["installation_id"],
        "status": "written",
        "request_id": "write-once",
    }
    for _ in range(2):
        assert api_post(client, "/installations", body).status_code == 200
    body.update(status="discovered", request_id="discover-once")
    for _ in range(2):
        assert api_post(client, "/installations", body).status_code == 200
    totals = client.get("/api/v1/skills/git-commit-guide/stats").json()["data"]["totals"]
    assert totals["installations"] == totals["discoveries"] == 1
    assert totals["downloads"] == 0  # plans and inline installation are not ZIP downloads


def test_analytics_rechecks_acl_and_respects_period(client, app):
    login(client)
    assert client.get("/api/v1/skills/java-code-review").status_code == 200
    with app.state.hub.repo.transaction() as tx:
        next(iter(tx["usage_events"].values()))["time"] = (
            datetime.now(timezone.utc) - timedelta(days=40)
        ).isoformat()
    assert client.get("/api/v1/analytics?days=30").json()["data"]["totals"]["detail_views"] == 0
    assert client.get("/api/v1/analytics?days=90").json()["data"]["totals"]["detail_views"] == 1
    login(client, "admin")
    changed = api_post(
        client,
        "/admin/teams/team-dev-a/members",
        {"user_id": "user-lisi", "role": "member", "status": "active"},
    )
    assert changed.status_code == 200
    login(client, "lisi")
    assert client.get("/api/v1/skills/java-code-review/stats?days=90").status_code == 200
    login(client, "admin")
    assert (
        api_post(
            client,
            "/admin/teams/team-dev-a/members",
            {"user_id": "user-lisi", "role": "member", "status": "removed"},
        ).status_code
        == 200
    )
    login(client, "lisi")
    assert client.get("/api/v1/skills/java-code-review/stats?days=90").status_code == 404
    assert client.get("/api/v1/analytics?days=0").status_code == 422
    assert client.get("/api/v1/analytics?days=366").status_code == 422


def test_analytics_requires_identity(client):
    assert client.get("/api/v1/analytics").status_code == 401

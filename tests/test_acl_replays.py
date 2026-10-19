from conftest import api_post, login, publish, skill_md


def test_older_publication_cannot_restore_revoked_sharing(client):
    publish(client, version="1.0.0", visibility="enterprise")
    login(client)
    assert (
        api_post(
            client,
            "/skills",
            {
                "team_id": "team-dev-a",
                "skill_id": "test-helper",
                "version": "0.9.0",
                "skill_md": skill_md(),
                "visibility": "enterprise",
            },
        ).status_code
        == 200
    )
    old_review = api_post(client, "/skills/test-helper/reviews", {"version": "0.9.0"}).json()["data"]
    assert (
        api_post(client, "/skills/test-helper/sharing/revoke", {"visibility": "private"}).status_code == 200
    )
    login(client, "admin")
    assert (
        api_post(
            client, "/reviews/" + old_review["review_id"] + "/decision", {"decision": "approved"}
        ).status_code
        == 200
    )
    detail = client.get("/api/v1/skills/test-helper").json()["data"]
    assert detail["current_version"] == "1.0.0" and detail["visibility"] == "private"
    login(client, "lisi")
    assert client.get("/api/v1/skills/test-helper").status_code == 404


def test_idempotent_replay_rechecks_current_team_permission(client):
    login(client, "admin")
    assert (
        api_post(
            client, "/admin/teams/team-dev-a/members", {"user_id": "user-wangwu", "role": "member"}
        ).status_code
        == 200
    )
    login(client, "wangwu")
    payload = {
        "team_id": "team-dev-a",
        "skill_md": skill_md("cached-helper"),
        "request_id": "cached-team-create",
    }
    assert api_post(client, "/skills", payload).status_code == 200
    login(client, "admin")
    assert (
        api_post(
            client,
            "/admin/teams/team-dev-a/members",
            {"user_id": "user-wangwu", "role": "member", "status": "removed"},
        ).status_code
        == 200
    )
    login(client, "wangwu")
    assert api_post(client, "/skills", payload).status_code == 403

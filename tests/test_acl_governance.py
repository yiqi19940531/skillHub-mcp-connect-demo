from conftest import api_post, authorize, login, publish, rpc, skill_md, upload


def test_rest_mcp_permissions_categories_and_favorites(client):
    token = authorize(client)
    rest = client.get("/api/v1/skills").json()["data"]
    mcp = rpc(client, token["access_token"], "search_skills", {"query": ""})["structuredContent"]["data"]
    assert {s["skill_id"] for s in rest["items"]} == {s["skill_id"] for s in mcp["items"]}
    assert rest["total"] == 5
    assert sum(c["count"] for c in client.get("/api/v1/categories").json()["data"]) == 5
    assert len(client.get("/api/v1/favorites").json()["data"]) == 2
    api_post(client, "/favorites", {"skill_id": "git-commit-guide"})
    login(client, "lisi")
    assert len(client.get("/api/v1/favorites").json()["data"]) == 2
    for path in [
        "/skills/java-code-review",
        "/skills/java-code-review/versions",
        "/skills/java-code-review/versions/1.0.0/files/SKILL.md",
    ]:
        response = client.get("/api/v1" + path)
        assert (
            response.status_code == 404
            and response.json()["error"]["code"] == "SKILL_NOT_FOUND_OR_NOT_ACCESSIBLE"
        )
    assert client.get("/api/v1/collections/col-dev-a/skills").status_code == 404
    assert api_post(client, "/skills", {"team_id": "team-dev-a", "skill_md": skill_md()}).status_code == 403


def test_draft_freeze_publishing_new_version_and_immutability(client):
    publish(client)
    login(client)
    created = upload(client, skill_id="test-helper", version="0.2.0")
    assert created.status_code == 200
    assert client.get("/api/v1/skills/test-helper").json()["data"]["current_version"] == "0.1.0"
    reviewed = api_post(client, "/skills/test-helper/reviews", {"version": "0.2.0"}).json()["data"]
    assert upload(client, skill_id="test-helper", version="0.2.0").status_code == 409
    assert (
        api_post(
            client, "/reviews/" + reviewed["review_id"] + "/decision", {"decision": "approved"}
        ).status_code
        == 403
    )
    login(client, "admin")
    assert (
        api_post(
            client, "/reviews/" + reviewed["review_id"] + "/decision", {"decision": "approved"}
        ).status_code
        == 200
    )
    assert client.get("/api/v1/skills/test-helper").json()["data"]["current_version"] == "0.2.0"
    login(client)
    assert upload(client, skill_id="test-helper", version="0.2.0").status_code == 409
    assert upload(client).status_code == 409


def test_admin_cannot_self_approve_and_rejection_can_be_edited(client):
    login(client, "admin")
    assert upload(client).status_code == 200
    review = api_post(client, "/skills/test-helper/reviews", {"version": "0.1.0"}).json()["data"]
    assert (
        api_post(
            client, "/reviews/" + review["review_id"] + "/decision", {"decision": "approved"}
        ).status_code
        == 403
    )
    api_post(
        client,
        "/admin/users",
        {
            "username": "reviewer",
            "display_name": "独立审核人",
            "password": "Reviewer@123456",
            "roles": ["Reviewer"],
        },
    ).json()["data"]
    login(client, "reviewer", "Reviewer@123456")
    assert (
        api_post(
            client,
            "/reviews/" + review["review_id"] + "/decision",
            {"decision": "rejected", "reason": "请完善说明"},
        ).status_code
        == 200
    )
    login(client, "admin")
    assert upload(client, extra_field="spoof").status_code == 422
    assert upload(client).status_code == 409
    assert upload(client, skill_id="test-helper").status_code == 200


def test_sharing_requires_team_owner_and_enterprise_requires_admin(client):
    publish(client)
    # Add Li Si as a different owner of dev-a. Zhang San remains an author/member.
    assert (
        api_post(
            client, "/admin/teams/team-dev-a/members", {"user_id": "user-lisi", "role": "owner"}
        ).status_code
        == 200
    )
    login(client)
    proposal = api_post(
        client,
        "/skills/test-helper/sharing",
        {"visibility": "custom", "acl": [{"type": "team", "id": "team-ops"}]},
    ).json()["data"]
    login(client, "wangwu")
    assert client.get("/api/v1/skills/test-helper").status_code == 404
    login(client, "lisi")
    assert (
        api_post(
            client, "/reviews/" + proposal["review_id"] + "/decision", {"decision": "approved"}
        ).status_code
        == 200
    )
    login(client, "wangwu")
    assert client.get("/api/v1/skills/test-helper").status_code == 200
    login(client)
    enterprise = api_post(client, "/skills/test-helper/sharing", {"visibility": "enterprise"}).json()["data"]
    login(client, "lisi")
    assert (
        api_post(
            client, "/reviews/" + enterprise["review_id"] + "/decision", {"decision": "approved"}
        ).status_code
        == 403
    )
    login(client, "admin")
    assert (
        api_post(
            client, "/reviews/" + enterprise["review_id"] + "/decision", {"decision": "approved"}
        ).status_code
        == 200
    )
    login(client)
    assert (
        api_post(client, "/skills/test-helper/sharing/revoke", {"visibility": "private"}).status_code == 200
    )
    login(client, "wangwu")
    assert client.get("/api/v1/skills/test-helper").status_code == 404


def test_collection_never_expands_access_and_filters_after_revoke(client):
    login(client, "admin")
    assert (
        api_post(client, "/collections/col-dev-b/skills", {"skill_id": "java-code-review"}).status_code == 409
    )
    before = client.get("/api/v1/collections/col-dev-a/skills").json()["data"]
    assert len(before) == 2
    login(client)
    api_post(client, "/skills/java-code-review/sharing/revoke", {"visibility": "private"})
    login(client, "admin")
    api_post(client, "/admin/teams/team-dev-a/members", {"user_id": "user-lisi", "role": "owner"})
    login(client, "lisi")
    rows = client.get("/api/v1/collections/col-dev-a/skills").json()["data"]
    assert [s["skill_id"] for s in rows] == ["git-commit-guide"]
    assert (
        next(
            c for c in client.get("/api/v1/collections").json()["data"] if c["collection_id"] == "col-dev-a"
        )["count"]
        == 1
    )


def test_ratings_feedback_recommendations_and_revoke(client):
    publish(client)
    login(client)
    for score in [3, 5]:
        assert (
            api_post(client, "/skills/test-helper/ratings", {"version": "0.1.0", "score": score}).status_code
            == 200
        )
    detail = client.get("/api/v1/skills/test-helper").json()["data"]
    assert detail["rating_count"] == 1 and detail["rating"] == 5
    issue = api_post(
        client, "/skills/test-helper/issues", {"description": "需要补充边界示例", "kind": "description"}
    ).json()["data"]
    assert (
        api_post(
            client,
            "/issues/" + issue["issue_id"],
            {"revision": 1, "status": "resolved", "resolution": "已在新草稿补充"},
            method="PATCH",
        ).status_code
        == 200
    )
    login(client, "lisi")
    assert client.get("/api/v1/issues").json()["data"] == []
    assert all(
        s["skill_id"] not in {"java-code-review", "test-helper"}
        for s in client.get("/api/v1/recommendations").json()["data"]
    )
    login(client)
    assert (
        api_post(client, "/skills/test-helper/versions/0.1.0/status", {"status": "deprecated"}).status_code
        == 200
    )
    assert "test-helper" not in [s["skill_id"] for s in client.get("/api/v1/skills").json()["data"]["items"]]
    assert (
        api_post(
            client, "/installations/plan", {"skill_id": "test-helper", "version": "0.1.0", "client": "codex"}
        ).status_code
        == 409
    )
    assert (
        api_post(client, "/skills/test-helper/versions/0.1.0/status", {"status": "revoked"}).status_code
        == 200
    )

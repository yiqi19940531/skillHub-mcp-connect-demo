from conftest import api_post, authorize, login


def test_account_and_team_management_last_admin(client):
    login(client)
    assert client.get("/api/v1/admin/users").status_code == 403
    login(client, "admin")
    admin = next(u for u in client.get("/api/v1/admin/users").json()["data"] if u["username"] == "admin")
    assert "password_hash" not in admin
    assert (
        api_post(
            client, "/admin/users/user-admin", {"revision": admin["revision"], "disabled": True}, "PATCH"
        ).json()["error"]["code"]
        == "LAST_ADMIN"
    )
    user = api_post(
        client,
        "/admin/users",
        {"username": "newmember", "display_name": "新成员", "password": "NewMember@123456"},
    ).json()["data"]
    team = api_post(client, "/admin/teams", {"name": "新团队", "owner_user_id": user["user_id"]}).json()[
        "data"
    ]
    assert team["name"] == "新团队"
    assert (
        api_post(
            client,
            "/admin/teams/" + team["team_id"],
            {"revision": team["revision"], "archived": True},
            "PATCH",
        ).status_code
        == 200
    )
    assert (
        api_post(
            client, "/admin/teams/" + team["team_id"] + "/members", {"user_id": "user-zhangsan"}
        ).status_code
        == 409
    )
    assert (
        api_post(
            client, "/admin/users/" + user["user_id"] + "/password", {"password": "Replacement@123456"}
        ).status_code
        == 200
    )
    login(client, "newmember", "Replacement@123456")
    assert client.get("/api/v1/me").json()["data"]["teams"][0]["archived"]


def test_disable_and_reset_password_revoke_old_credentials(client):
    token = authorize(client)
    login(client, "admin")
    assert (
        api_post(client, "/admin/users/user-zhangsan/password", {"password": "Changed@123456"}).status_code
        == 200
    )
    assert (
        client.get("/api/v1/me", headers={"Authorization": "Bearer " + token["access_token"]}).status_code
        == 401
    )
    token = authorize(client, "zhangsan", "Changed@123456")
    login(client, "admin")
    user = next(u for u in client.get("/api/v1/admin/users").json()["data"] if u["username"] == "zhangsan")
    assert (
        api_post(
            client, "/admin/users/user-zhangsan", {"revision": user["revision"], "disabled": True}, "PATCH"
        ).status_code
        == 200
    )
    assert (
        client.get("/api/v1/me", headers={"Authorization": "Bearer " + token["access_token"]}).status_code
        == 401
    )

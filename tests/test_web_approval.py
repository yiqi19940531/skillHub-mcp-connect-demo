from conftest import api_post, authorize, login, upload


def test_mcp_bearer_cannot_bypass_web_approval_channel(client):
    login(client)
    assert upload(client).status_code == 200
    review = api_post(client, "/skills/test-helper/reviews", {"version": "0.1.0"}).json()["data"]
    manager = authorize(client, "admin")
    response = client.post(
        "/api/v1/reviews/" + review["review_id"] + "/decision",
        json={"decision": "approved"},
        headers={
            "Authorization": "Bearer " + manager["access_token"],
            "x-csrf-token": client.cookies["skillhub_csrf"],
        },
    )
    assert response.status_code == 403 and response.json()["error"]["code"] == "WEB_APPROVAL_REQUIRED"
    assert not response.json()["error"]["retryable"]
    assert (
        api_post(
            client, "/reviews/" + review["review_id"] + "/decision", {"decision": "approved"}
        ).status_code
        == 200
    )

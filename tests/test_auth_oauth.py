import re
from urllib.parse import parse_qs, urlsplit

import jwt
import pytest

from conftest import BASE, api_post, authorize, begin_oauth, login, rpc
from backend.app.auth.oauth import redirect_matches
from backend.app.main import create_app
from fastapi.testclient import TestClient


def test_login_logout_csrf_and_validation_redaction(client):
    assert client.get("/api/v1/me").status_code == 401
    login(client)
    assert client.get("/api/v1/me").json()["data"]["username"] == "zhangsan"
    assert client.post("/api/v1/favorites", json={"skill_id": "git-commit-guide"}).status_code == 403
    assert api_post(client, "/favorites", {"skill_id": "git-commit-guide"}).status_code == 200
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "bad"},
            headers={"origin": "https://untrusted.example"},
        ).status_code
        == 403
    )
    secret = "must-never-be-echoed" * 20
    invalid = client.post("/api/v1/auth/login", json={"username": "admin", "password": secret})
    assert invalid.status_code == 422 and secret not in invalid.text
    assert api_post(client, "/auth/logout", {}).status_code == 200
    assert client.get("/api/v1/me").status_code == 401


def test_oauth_discovery_redirect_real_subject_and_account_switch(client):
    missing = client.post("/mcp", json={})
    assert missing.status_code == 401 and "resource_metadata" in missing.headers["www-authenticate"]
    for path in ["/.well-known/oauth-protected-resource", "/.well-known/oauth-protected-resource/mcp"]:
        assert client.get(path).json()["resource"] == BASE + "/mcp"
    metadata = client.get("/.well-known/oauth-authorization-server").json()
    assert metadata["authorization_response_iss_parameter_supported"]
    assert not metadata.get("client_id_metadata_document_supported")
    _, _, _, response = begin_oauth(client)
    assert response.status_code == 303 and response.headers["location"].startswith("/app/login?")
    token = authorize(client)
    result = rpc(client, token["access_token"], "whoami")
    assert result["structuredContent"]["data"]["username"] == "zhangsan"
    login(client, "lisi")
    assert rpc(client, token["access_token"], "whoami")["structuredContent"]["data"]["username"] == "zhangsan"
    second = authorize(client, "lisi")
    assert rpc(client, second["access_token"], "whoami")["structuredContent"]["data"]["username"] == "lisi"
    assert client.post("/mcp", json={}).status_code == 401  # Cookie alone is never MCP auth.


@pytest.mark.parametrize(
    "change",
    [
        {"redirect_uri": "http://127.0.0.1:1/wrong"},
        {"resource": "https://wrong.example/mcp"},
        {"code_challenge_method": "plain"},
        {"state": ""},
    ],
)
def test_authorization_rejects_invalid_parameters(client, change):
    login(client)
    _, _, params, _ = begin_oauth(client)
    assert client.get("/oauth/authorize", params={**params, **change}).status_code == 400


def test_code_one_use_pkce_and_audience(client, app):
    token = authorize(client)
    assert client.post("/oauth/token", data=token["exchange_form"]).status_code == 400
    login(client)
    client_id, verifier, params, response = begin_oauth(client)
    request_id = re.search(r'name="request_id" value="([^"]+)"', response.text).group(1)
    response = client.post(
        "/oauth/authorize",
        data={"request_id": request_id, "csrf": client.cookies["skillhub_csrf"], "decision": "approve"},
        follow_redirects=False,
    )
    code = parse_qs(urlsplit(response.headers["location"]).query)["code"][0]
    exchange = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "redirect_uri": params["redirect_uri"],
        "resource": BASE + "/mcp",
        "code": code,
        "code_verifier": "x" * 64,
    }
    assert client.post("/oauth/token", data=exchange).status_code == 400
    exchange["code_verifier"] = verifier
    assert client.post("/oauth/token", data=exchange).status_code == 200
    claims = jwt.decode(token["access_token"], options={"verify_signature": False})
    for changed in [{"aud": BASE + "/other"}, {"iss": BASE + "/wrong"}, {"exp": 1}]:
        raw = jwt.encode({**claims, **changed}, app.state.identity.key, algorithm="HS256")
        assert client.get("/api/v1/me", headers={"Authorization": "Bearer " + raw}).status_code == 401


def test_refresh_rotation_replay_revokes_grant(client):
    token = authorize(client)
    form = {
        "grant_type": "refresh_token",
        "refresh_token": token["refresh_token"],
        "client_id": token["client_id"],
    }
    refreshed = client.post("/oauth/token", data=form)
    assert refreshed.status_code == 200 and refreshed.json()["refresh_token"] != token["refresh_token"]
    assert client.post("/oauth/token", data=form).status_code == 400
    assert (
        client.get(
            "/api/v1/me", headers={"Authorization": "Bearer " + refreshed.json()["access_token"]}
        ).status_code
        == 401
    )


def test_user_grant_revocation_and_scope_boundary(client):
    token = authorize(client, scope="skills:read")
    denied = rpc(client, token["access_token"], "add_favorite", {"skill_id": "git-commit-guide"})
    assert denied["isError"] and denied["structuredContent"]["error"]["code"] == "FORBIDDEN"
    grants = client.get("/api/v1/oauth/grants").json()["data"]
    assert api_post(client, "/oauth/grants/" + grants[0]["grant_id"], {}, method="DELETE").status_code == 200
    assert (
        client.get("/api/v1/me", headers={"Authorization": "Bearer " + token["access_token"]}).status_code
        == 401
    )


def test_tokens_survive_restart_but_tickets_and_codes_do_not(tmp_path):
    from backend.app.config import Settings

    config = Settings(data_dir=tmp_path / "restart")
    first = create_app(config)
    with TestClient(first, base_url=BASE) as c:
        token = authorize(c)
        plan = api_post(
            c, "/installations/plan", {"skill_id": "git-commit-guide", "client": "codex-desktop"}
        ).json()["data"]
    second = create_app(config)
    with TestClient(second, base_url=BASE) as c:
        assert (
            c.get("/api/v1/me", headers={"Authorization": "Bearer " + token["access_token"]}).status_code
            == 200
        )
        assert c.get(plan["package"]["download_url"]).status_code == 410
        assert (
            c.post(
                "/oauth/token",
                data={
                    "grant_type": "refresh_token",
                    "client_id": token["client_id"],
                    "refresh_token": token["refresh_token"],
                },
            ).status_code
            == 200
        )


def test_native_callback_matching_is_exact_except_loopback_port():
    assert redirect_matches("http://127.0.0.1/callback", "http://127.0.0.1:43210/callback")
    assert not redirect_matches("http://127.0.0.1/callback", "http://127.0.0.1:43210/other")
    assert not redirect_matches("http://127.0.0.1/callback", "http://localhost:43210/callback")
    assert not redirect_matches("https://example.com/callback", "https://example.com:444/callback")
    assert not redirect_matches("http://127.0.0.1/callback", "http://evil.example/callback")


def test_opaque_origin_consent_still_requires_csrf(client):
    login(client)
    _, _, _, response = begin_oauth(client)
    request_id = re.search(r'name="request_id" value="([^"]+)"', response.text).group(1)
    data = {"request_id": request_id, "decision": "approve"}
    assert client.post("/oauth/authorize", data=data, headers={"origin": "null"}).status_code == 403
    data["csrf"] = client.cookies["skillhub_csrf"]
    assert (
        client.post("/oauth/authorize", data=data, headers={"origin": "https://evil.example"}).status_code
        == 403
    )
    assert (
        client.post(
            "/oauth/authorize", data=data, headers={"origin": "null"}, follow_redirects=False
        ).status_code
        == 303
    )


def test_public_revocation_endpoint_accepts_access_tokens(client):
    token = authorize(client)
    assert (
        client.post(
            "/oauth/revoke", data={"client_id": token["client_id"], "token": token["access_token"]}
        ).status_code
        == 200
    )
    assert (
        client.get("/api/v1/me", headers={"Authorization": "Bearer " + token["access_token"]}).status_code
        == 401
    )

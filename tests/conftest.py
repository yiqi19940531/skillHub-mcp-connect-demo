import socket
import threading
import time
import uvicorn
import base64
import hashlib
import re
from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient
import pytest

from backend.app.config import Settings
from backend.app.main import create_app

BASE = "http://127.0.0.1:8765"
PASSWORDS = {
    "admin": "Admin@123456",
    "zhangsan": "ZhangSan@123456",
    "lisi": "LiSi@123456",
    "wangwu": "WangWu@123456",
    "zhaoliu": "ZhaoLiu@123456",
}


@pytest.fixture
def app(tmp_path):
    return create_app(Settings(data_dir=tmp_path / "data"))


@pytest.fixture
def client(app):
    with TestClient(app, base_url=BASE) as client:
        yield client


def login(client, username="zhangsan", password=None):
    response = client.post(
        "/api/v1/auth/login", json={"username": username, "password": password or PASSWORDS[username]}
    )
    assert response.status_code == 200
    return {"x-csrf-token": client.cookies.get("skillhub_csrf")}


def api_post(client, path, payload, method="POST"):
    return client.request(
        method,
        "/api/v1" + path,
        json=payload,
        headers={"x-csrf-token": client.cookies.get("skillhub_csrf", "")},
    )


def begin_oauth(client, scope="skills:read skills:write", redirect="http://127.0.0.1:54321/callback"):
    registered = client.post(
        "/oauth/register", json={"client_name": "HTTP test client", "redirect_uris": [redirect]}
    )
    assert registered.status_code == 201
    client_id = registered.json()["client_id"]
    verifier = "v" * 64
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    params = {
        "client_id": client_id,
        "redirect_uri": redirect,
        "response_type": "code",
        "scope": scope,
        "state": "test-state-not-a-token",
        "code_challenge_method": "S256",
        "code_challenge": challenge,
        "resource": str(client.base_url).rstrip("/") + "/mcp",
    }
    response = client.get("/oauth/authorize", params=params, follow_redirects=False)
    return client_id, verifier, params, response


def authorize(client, username="zhangsan", password=None, scope="skills:read skills:write"):
    login(client, username, password)
    client_id, verifier, params, response = begin_oauth(client, scope)
    assert response.status_code == 200
    request_id = re.search(r'name="request_id" value="([^"]+)"', response.text).group(1)
    approved = client.post(
        "/oauth/authorize",
        data={"request_id": request_id, "csrf": client.cookies.get("skillhub_csrf"), "decision": "approve"},
        follow_redirects=False,
    )
    assert approved.status_code == 303
    query = parse_qs(urlsplit(approved.headers["location"]).query)
    assert query["state"] == [params["state"]]
    assert query["iss"] == [str(client.base_url).rstrip("/")]
    form = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "redirect_uri": params["redirect_uri"],
        "resource": str(client.base_url).rstrip("/") + "/mcp",
        "code": query["code"][0],
        "code_verifier": verifier,
    }
    response = client.post("/oauth/token", data=form)
    assert response.status_code == 200
    return {**response.json(), "client_id": client_id, "exchange_form": form}


def rpc(client, token, name, arguments=None):
    response = client.post(
        "/mcp",
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/json, text/event-stream",
            "Mcp-Protocol-Version": "2025-11-25",
        },
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        },
    )
    assert response.status_code == 200
    return response.json()["result"]


def skill_md(name="test-helper", extra=""):
    return f"---\nname: {name}\ndescription: Help the team review a repeatable workflow.\n---\n\n# Helper\n\nCheck the result.\n{extra}"


def upload(client, name="test-helper", **changes):
    return api_post(
        client,
        "/skills",
        {
            "team_id": "team-dev-a",
            "skill_md": skill_md(name),
            "visibility": "team",
            "version": "0.1.0",
            **changes,
        },
    )


def publish(client, name="test-helper", **changes):
    login(client)
    created = upload(client, name, **changes)
    assert created.status_code == 200
    version = changes.get("version", "0.1.0")
    reviewed = api_post(client, "/skills/" + name + "/reviews", {"version": version})
    assert reviewed.status_code == 200
    review_id = reviewed.json()["data"]["review_id"]
    login(client, "admin")
    response = api_post(client, "/reviews/" + review_id + "/decision", {"decision": "approved"})
    assert response.status_code == 200
    return response.json()["data"]


@pytest.fixture
def live_server(tmp_path):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    app = create_app(Settings(data_dir=tmp_path / "live-data", base_url=url))
    server = uvicorn.Server(uvicorn.Config(app, access_log=False, log_level="warning"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.025)
        assert server.started
        yield url, app
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()

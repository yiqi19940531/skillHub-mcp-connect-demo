import base64
import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import pytest


@pytest.fixture
def native_callback():
    class Receiver(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<p>Native OAuth callback received.</p>")

        def log_message(self, *args):
            pass  # Authorization codes and browser cookies must not enter access logs.

    server = ThreadingHTTPServer(("127.0.0.1", 0), Receiver)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/test-callback"
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)


@pytest.mark.skipif(
    not Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome").exists(),
    reason="需要本机 Chrome",
)
def test_browser_oauth_redirect_origin_and_token_exchange(live_server, native_callback):
    from playwright.sync_api import sync_playwright, expect

    url, app = live_server
    verifier = "browser-verifier-" + "v" * 48
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    redirect = native_callback
    assert urlsplit(redirect).port != urlsplit(url).port
    with httpx.Client(base_url=url, trust_env=False) as client:
        client_id = client.post(
            "/oauth/register", json={"client_name": "Browser OAuth test", "redirect_uris": [redirect]}
        ).json()["client_id"]
        params = {
            "client_id": client_id,
            "redirect_uri": redirect,
            "response_type": "code",
            "resource": url + "/mcp",
            "scope": "skills:read skills:write",
            "state": "browser-test-state",
            "code_challenge_method": "S256",
            "code_challenge": challenge,
        }
        origins = []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome", headless=True)
            page = browser.new_page()
            page.on(
                "request",
                lambda request: (
                    origins.append(request.headers.get("origin"))
                    if request.method == "POST" and request.url == url + "/oauth/authorize"
                    else None
                ),
            )
            page.goto(url + "/oauth/authorize?" + urlencode(params))
            page.get_by_role("button", name="张 张三 研发一组", exact=True).click()
            page.get_by_role("button", name="登录 Skill Hub", exact=True).click()
            expect(page.get_by_role("heading", name="授权连接你的技能库", exact=True)).to_be_visible()
            page.get_by_role("button", name="同意并连接", exact=True).click()
            page.wait_for_url("**/test-callback?**")
            query = parse_qs(urlsplit(page.url).query)
            assert query["state"] == ["browser-test-state"] and query["iss"] == [url]
            assert origins and origins[0] in {url, "null"}
            Path("test-results/browser-oauth.json").write_text(
                json.dumps(
                    {
                        "browser": "Chrome (isolated Playwright profile)",
                        "consent_origin": origins[0],
                        "pkce": "S256",
                        "state_matched": True,
                        "issuer_matched": True,
                        "cross_port_native_callback": True,
                    }
                )
            )
            token = client.post(
                "/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": client_id,
                    "redirect_uri": redirect,
                    "resource": url + "/mcp",
                    "code": query["code"][0],
                    "code_verifier": verifier,
                },
            )
            assert token.status_code == 200
            assert (
                client.get(
                    "/api/v1/me", headers={"Authorization": "Bearer " + token.json()["access_token"]}
                ).json()["data"]["username"]
                == "zhangsan"
            )
            browser.close()

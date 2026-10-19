"""Real loopback TCP and browser workflows. Local file writes are a test Agent simulation,
not evidence that Qoder/Codex desktop has discovered a skill.
"""

from io import BytesIO
import json
from pathlib import Path
import zipfile

import httpx
import pytest

from backend.app.security.packages import digest
from conftest import api_post, authorize, rpc, skill_md


def test_real_http_agent_install_upload_update_uninstall(live_server, tmp_path):
    url, app = live_server
    with httpx.Client(base_url=url, trust_env=False) as client:
        token = authorize(client)
        raw_token = token["access_token"]
        plan = rpc(
            client,
            raw_token,
            "install_skill",
            {"skill_id": "git-commit-guide", "client": "codex-desktop", "workspace_id": "http-test"},
        )["structuredContent"]["data"]
        downloaded = client.get(plan["package"]["download_url"])
        assert downloaded.status_code == 200 and digest(downloaded.content) == plan["sha256"]
        target = tmp_path / "agent-workspace" / ".agents" / "skills" / "git-commit-guide"
        target.mkdir(parents=True)
        with zipfile.ZipFile(BytesIO(downloaded.content)) as archive:
            assert set(archive.namelist()) == {f["path"] for f in plan["manifest"]}
            for entry in plan["manifest"]:
                body = archive.read(entry["path"])
                assert digest(body) == entry["sha256"]
                local = target / entry["path"]
                local.parent.mkdir(parents=True, exist_ok=True)
                local.write_bytes(body)
        (target / ".skill-hub-install.json").write_text(json.dumps(plan["receipt"]))
        assert (target / "SKILL.md").is_file()
        report = {
            "skill_id": "git-commit-guide",
            "version": plan["version"],
            "client": "codex-desktop",
            "scope": "project",
            "installation_id": plan["installation_id"],
            "status": "written",
            "digest": plan["sha256"],
            "files_written": True,
        }
        assert rpc(client, raw_token, "report_install_result", report)["structuredContent"]["ok"]
        # Text and binary uploads both go through the real HTTP MCP endpoint.
        assert (
            rpc(
                client,
                raw_token,
                "upload_skill",
                {"team_id": "team-dev-a", "skill_md": skill_md("http-helper"), "request_id": "http-once"},
            )["structuredContent"]["data"]["status"]
            == "draft"
        )
        review = rpc(
            client, raw_token, "request_skill_review", {"skill_id": "http-helper", "version": "0.1.0"}
        )["structuredContent"]["data"]
        authorize(client, "admin")
        assert (
            api_post(
                client, "/reviews/" + review["review_id"] + "/decision", {"decision": "approved"}
            ).status_code
            == 200
        )
        # Update an existing author's version, approve, then observe update availability.
        user_token = authorize(client)
        plan2 = rpc(
            client,
            user_token["access_token"],
            "install_skill",
            {"skill_id": "http-helper", "client": "qoder-ide"},
        )["structuredContent"]["data"]
        assert rpc(
            client,
            user_token["access_token"],
            "report_install_result",
            {
                "skill_id": "http-helper",
                "version": "0.1.0",
                "client": "qoder-ide",
                "scope": "project",
                "installation_id": plan2["installation_id"],
                "status": "written",
            },
        )["structuredContent"]["ok"]
        assert rpc(
            client,
            user_token["access_token"],
            "upload_skill",
            {
                "team_id": "team-dev-a",
                "skill_id": "http-helper",
                "skill_md": skill_md("http-helper", "New version."),
                "version": "0.2.0",
            },
        )["structuredContent"]["ok"]
        newer = rpc(
            client,
            user_token["access_token"],
            "request_skill_review",
            {"skill_id": "http-helper", "version": "0.2.0"},
        )["structuredContent"]["data"]
        authorize(client, "admin")
        assert (
            api_post(
                client, "/reviews/" + newer["review_id"] + "/decision", {"decision": "approved"}
            ).status_code
            == 200
        )
        updates = rpc(client, user_token["access_token"], "check_skill_updates")["structuredContent"]["data"]
        assert any(item["skill_id"] == "http-helper" and item["update_available"] for item in updates)
        update = rpc(
            client, user_token["access_token"], "update_skill", {"installation_id": plan2["installation_id"]}
        )["structuredContent"]["data"]
        assert update["version"] == "0.2.0" and update["expected_local_manifest"]
        # Uninstall only receipt files; an unrelated user file must survive.
        (target / "personal-note.txt").write_text("preserve me")
        uninstall = rpc(client, raw_token, "uninstall_skill", {"installation_id": plan["installation_id"]})[
            "structuredContent"
        ]["data"]
        for entry in uninstall["manifest"]:
            local = target / entry["path"]
            assert digest(local.read_bytes()) == entry["sha256"]
            local.unlink()
        (target / ".skill-hub-install.json").unlink()
        assert (target / "personal-note.txt").read_text() == "preserve me"
        assert rpc(
            client,
            raw_token,
            "report_install_result",
            {
                **report,
                "installation_id": uninstall["installation_id"],
                "operation": "uninstall",
                "status": "uninstalled",
                "files_written": False,
            },
        )["structuredContent"]["ok"]


def test_all_mcp_tool_schemas_and_readonly_contract(client):
    token = authorize(client)
    response = client.post(
        "/mcp",
        headers={
            "Authorization": "Bearer " + token["access_token"],
            "Accept": "application/json, text/event-stream",
            "Mcp-Protocol-Version": "2025-11-25",
        },
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
    )
    tools = response.json()["result"]["tools"]
    assert len(tools) == 32 and len({t["name"] for t in tools}) == 32
    assert not any(t["name"] == "login" for t in tools)
    assert next(t for t in tools if t["name"] == "get_skill_install_plan")["annotations"]["readOnlyHint"]
    for name, args in [
        ("whoami", {}),
        ("list_my_teams", {}),
        ("list_skill_categories", {}),
        ("list_skills", {}),
        ("search_skills", {"query": "git"}),
        ("get_skill", {"skill_id": "git-commit-guide"}),
        ("get_skill_instructions", {"skill_id": "git-commit-guide"}),
        ("get_skill_file", {"skill_id": "git-commit-guide", "version": "1.0.0", "relative_path": "SKILL.md"}),
        ("list_skill_versions", {"skill_id": "git-commit-guide"}),
        ("list_favorites", {}),
        ("list_collections", {}),
        ("list_collection_skills", {"collection_id": "col-dev-a"}),
        ("get_skill_install_plan", {"skill_id": "git-commit-guide", "client": "qoder-ide"}),
        ("list_installed_skills", {}),
        ("check_skill_updates", {}),
        ("list_my_uploads", {}),
        ("recommend_skills", {}),
    ]:
        result = rpc(client, token["access_token"], name, args)
        assert not result.get("isError"), name
        assert result["structuredContent"]["ok"], name


@pytest.mark.skipif(
    not Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome").exists(),
    reason="需要本机 Chrome",
)
def test_browser_upload_approval_isolation_and_management(live_server, tmp_path):
    from playwright.sync_api import sync_playwright, expect

    url, app = live_server
    errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1050})
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(url + "/app")
        page.get_by_role("button", name="张 张三 研发一组").click()
        page.get_by_role("button", name="登录 Skill Hub").click()
        expect(page.get_by_role("heading", name="发现 Skills 5")).to_be_visible()
        expect(page.get_by_text("会话已失效，请重新登录", exact=True)).not_to_be_visible()
        screenshots = Path("test-results/screenshots")
        screenshots.mkdir(parents=True, exist_ok=True)
        expect(page.get_by_role("heading", name="Java 代码审查清单", exact=True)).to_be_visible()
        page.screenshot(path=str(screenshots / "market-desktop.png"), full_page=True)
        page.get_by_role("button", name="收藏 Git Commit 说明规范", exact=True).click()
        page.get_by_role("button", name="我的收藏", exact=True).click()
        expect(page.get_by_role("heading", name="Git Commit 说明规范", exact=True)).to_be_visible()
        page.goto(url + "/app/upload")
        page.get_by_role("button", name="粘贴 SKILL.md").click()
        page.get_by_label("SKILL.md 内容").fill(skill_md("browser-helper"))
        page.get_by_label("显示名称", exact=True).fill("浏览器验收技能")
        page.get_by_role("button", name="检查并保存草稿").click()
        expect(page.get_by_role("heading", name="浏览器验收技能", exact=True)).to_be_visible()
        page.get_by_role("button", name="修改草稿", exact=True).click()
        expect(page.get_by_label("SKILL.md 内容", exact=True)).to_have_value(skill_md("browser-helper"))
        page.get_by_label("SKILL.md 内容", exact=True).fill(
            skill_md("browser-helper", "Revised instructions.")
        )
        page.get_by_role("button", name="检查并保存草稿").click()
        expect(page.get_by_role("heading", name="浏览器验收技能", exact=True)).to_be_visible()
        page.get_by_role("button", name="提交审核", exact=True).click()
        expect(page.get_by_text("待审核", exact=True)).to_be_visible()
        page.get_by_role("button", name="退出登录").click()
        page.get_by_role("button", name="管 管理员 平台管理").click()
        page.get_by_role("button", name="登录 Skill Hub").click()
        page.get_by_role("button", name="审核中心", exact=True).click()
        page.get_by_role("button", name="查看并审核").click()
        page.screenshot(path=str(screenshots / "review.png"), full_page=True)
        page.get_by_role("button", name="通过申请").click()
        expect(page.get_by_text("当前没有待处理申请", exact=True)).to_be_visible()
        page.get_by_role("button", name="成员与团队", exact=True).click()
        expect(page.get_by_role("heading", name="成员与团队", exact=True)).to_be_visible()
        page.get_by_role("button", name="编辑 张三", exact=True).click()
        page.get_by_label("显示姓名").fill("张三（验收）")
        page.get_by_role("button", name="保存账号", exact=True).click()
        expect(page.get_by_text("张三（验收）", exact=True)).to_be_visible()
        page.get_by_role("button", name="退出登录").click()
        page.get_by_role("button", name="李 李四 研发二组").click()
        page.get_by_role("button", name="登录 Skill Hub").click()
        expect(page.get_by_role("heading", name="发现 Skills 5")).to_be_visible()
        page.goto(url + "/app/skills/browser-helper")
        expect(page.get_by_text("Skill 不存在或当前用户无权访问", exact=True)).to_be_visible()
        assert not errors, errors
        context.close()
        browser.close()


@pytest.mark.skipif(
    not Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome").exists(),
    reason="需要本机 Chrome",
)
def test_browser_collection_revision_and_mobile_layout(live_server):
    from playwright.sync_api import sync_playwright, expect

    url, app = live_server
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(url + "/app")
        page.get_by_role("button", name="李 李四 研发二组", exact=True).click()
        page.get_by_role("button", name="登录 Skill Hub", exact=True).click()
        expect(page.get_by_role("heading", name="发现 Skills 5")).to_be_visible()
        page.get_by_role("button", name="团队收藏集", exact=True).click()
        page.get_by_role("button", name="新建收藏集", exact=True).click()
        page.get_by_label("收藏集名称", exact=True).fill("浏览器收藏集")
        page.get_by_role("button", name="保存收藏集", exact=True).click()
        page.get_by_role("button", name="浏览器收藏集", exact=False).click()
        page.get_by_role("button", name="添加 Skill", exact=True).click()
        page.get_by_label("选择 Skill", exact=True).select_option("git-commit-guide")
        page.get_by_role("button", name="添加到收藏集", exact=True).click()
        expect(page.get_by_role("button", name="移除 Git Commit 说明规范", exact=True)).to_be_visible()
        page.get_by_role("button", name="编辑", exact=True).click()
        page.get_by_label("收藏集名称", exact=True).fill("浏览器收藏集已改名")
        page.get_by_role("button", name="保存收藏集", exact=True).click()
        expect(page.get_by_role("heading", name="浏览器收藏集已改名", exact=True)).to_be_visible()
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(url + "/app")
        expect(page.get_by_role("heading", name="发现 Skills 5")).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        page.screenshot(path="test-results/screenshots/market-mobile.png", full_page=True)
        browser.close()

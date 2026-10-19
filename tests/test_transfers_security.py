from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import json
import stat
import zipfile

import pytest

from conftest import api_post, authorize, login, rpc, skill_md, upload
from backend.app.errors import HubError
from backend.app.security.packages import digest
from backend.app.storage.repository import Repository, atomic_write


def make_zip(entries):
    out = BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries:
            archive.writestr(name, content)
    return out.getvalue()


def test_two_step_zip_upload_and_review(client):
    login(client)
    raw = make_zip(
        [
            ("zip-helper/SKILL.md", skill_md("zip-helper")),
            ("zip-helper/references/guide.txt", "Read this guide."),
        ]
    )
    prepared = api_post(
        client,
        "/uploads/prepare",
        {"team_id": "team-dev-a", "filename": "helper.zip", "size": len(raw), "sha256": digest(raw)},
    ).json()["data"]
    assert client.post(prepared["upload_url"], content=raw).status_code == 200
    assert client.post(prepared["upload_url"], content=raw).status_code == 410
    created = api_post(
        client, "/skills", {"team_id": "team-dev-a", "upload_id": prepared["upload_id"], "version": "0.1.0"}
    )
    assert created.status_code == 200 and created.json()["data"]["status"] == "draft"
    assert len(created.json()["data"]["version"]["manifest"]) == 2
    repeated = api_post(
        client, "/skills", {"team_id": "team-dev-a", "upload_id": prepared["upload_id"], "version": "0.1.0"}
    )
    assert repeated.json()["data"] == created.json()["data"]
    changed = api_post(
        client, "/skills", {"team_id": "team-dev-a", "upload_id": prepared["upload_id"], "version": "0.2.0"}
    )
    assert changed.status_code == 409 and changed.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    login(client, "lisi")
    assert client.get("/api/v1/skills/zip-helper").status_code == 404


def test_web_multipart_uses_same_validation(client):
    headers = login(client)
    response = client.post(
        "/api/v1/uploads",
        files={"file": ("SKILL.md", skill_md("web-helper"))},
        data={"metadata": json.dumps({"team_id": "team-dev-a", "version": "0.1.0", "visibility": "team"})},
        headers=headers,
    )
    assert (
        response.status_code == 200 and response.json()["data"]["skill"]["owner_user_id"] == "user-zhangsan"
    )
    secret = skill_md("bad-helper", "-----BEGIN PRIVATE KEY-----")
    response = client.post(
        "/api/v1/uploads",
        files={"file": ("SKILL.md", secret)},
        data={"metadata": json.dumps({"team_id": "team-dev-a"})},
        headers=headers,
    )
    assert response.status_code == 400 and "PRIVATE KEY" not in response.text


@pytest.mark.parametrize(
    "path",
    [
        "../outside.txt",
        "/tmp/outside.txt",
        "a/../../outside.txt",
        "a\\b.txt",
        "C:/outside.txt",
        "./outside.txt",
    ],
)
def test_reject_unsafe_archive_paths(app, path):
    raw = make_zip([("SKILL.md", skill_md()), (path, "outside")])
    with pytest.raises(HubError) as problem:
        app.state.hub.packages.unpack(raw)
    assert problem.value.code == "UPLOAD_INVALID"


def test_archive_links_duplicates_and_bomb_are_rejected(app):
    out = BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr("SKILL.md", skill_md())
        link = zipfile.ZipInfo("link")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(link, "/etc/passwd")
    for raw in [
        out.getvalue(),
        make_zip([("SKILL.md", skill_md()), ("A.txt", "1"), ("a.txt", "2")]),
        make_zip([("SKILL.md", skill_md()), ("bomb.txt", "a" * 500_000)]),
        make_zip([("SKILL.md", skill_md()), ("file", "1"), ("file/child", "2")]),
    ]:
        with pytest.raises(HubError):
            app.state.hub.packages.unpack(raw)


@pytest.mark.parametrize(
    "extra", ["-----BEGIN RSA PRIVATE KEY-----", "api_key: 'a-long-sensitive-key-value'", "AKIA" + "A" * 16]
)
def test_credentials_blocked_and_not_echoed(client, extra):
    login(client)
    response = upload(client, skill_md=skill_md("test-helper", extra))
    assert response.status_code == 400 and extra not in response.text


def test_script_saved_with_risk_not_executed_and_bad_frontmatter_rejected(app):
    files = {"SKILL.md": skill_md().encode(), "scripts/test.sh": b"echo no-execution"}
    meta, warnings = app.state.hub.packages.validate(files)
    assert meta["name"] == "test-helper" and warnings[0]["rule"] == "script_present"
    for text in [
        "no frontmatter",
        "---\nname: &a test-helper\ndescription: *a\n---\n",
        "---\nname: foo\nname: bar\ndescription: x\n---\n",
    ]:
        with pytest.raises(HubError):
            app.state.hub.packages.validate({"SKILL.md": text.encode()})


def test_ticket_single_use_expiry_repermission_and_digest(client, app):
    login(client)
    before = len(app.state.hub.repo.snapshot()["installations"])
    pure = api_post(
        client, "/installations/preflight", {"skill_id": "git-commit-guide", "client": "codex-desktop"}
    )
    assert pure.status_code == 200 and "package" not in pure.json()["data"]
    assert len(app.state.hub.repo.snapshot()["installations"]) == before
    planned = api_post(
        client, "/installations/plan", {"skill_id": "git-commit-guide", "client": "codex-desktop"}
    ).json()["data"]
    url = planned["package"]["download_url"]
    response = client.get(url)
    assert response.status_code == 200 and digest(response.content) == planned["sha256"]
    assert client.get(url).status_code == 410
    expired = api_post(client, "/skills/git-commit-guide/download", {"version": "1.0.0"}).json()["data"]
    with app.state.hub.repo.transaction() as tx:
        for ticket in tx["tickets"].values():
            ticket["expires_at"] = 0
    assert client.get(expired["download_url"]).status_code == 410
    plan = api_post(
        client, "/installations/plan", {"skill_id": "java-code-review", "client": "qoder-ide"}
    ).json()["data"]
    # A different team member gets access, receives a ticket, then loses membership.
    login(client, "admin")
    api_post(client, "/admin/teams/team-dev-a/members", {"user_id": "user-wangwu", "role": "member"})
    login(client, "wangwu")
    plan = api_post(
        client, "/installations/plan", {"skill_id": "java-code-review", "client": "qoder-ide"}
    ).json()["data"]
    login(client, "admin")
    api_post(
        client,
        "/admin/teams/team-dev-a/members",
        {"user_id": "user-wangwu", "role": "member", "status": "removed"},
    )
    assert client.get(plan["package"]["download_url"]).status_code == 404
    login(client)
    corrupt = api_post(client, "/skills/git-commit-guide/download", {"version": "1.0.0"}).json()["data"]
    version = app.state.hub.repo.snapshot()["versions"]["git-commit-guide@1.0.0"]
    path = app.state.hub.settings.data_dir / version["bundle_path"]
    path.write_bytes(path.read_bytes() + b"tampered")
    assert client.get(corrupt["download_url"]).json()["error"]["code"] == "DIGEST_MISMATCH"


def test_agent_report_update_uninstall_and_owner_isolation(client):
    token = authorize(client)
    plan = rpc(
        client,
        token["access_token"],
        "install_skill",
        {"skill_id": "git-commit-guide", "client": "codex-desktop"},
    )["structuredContent"]["data"]
    assert (
        plan["status"] == "agent_action_required" and plan["target"]["base_relative_path"] == ".agents/skills"
    )
    report = {
        "skill_id": "git-commit-guide",
        "version": "1.0.0",
        "client": "codex-desktop",
        "scope": "project",
        "status": "discovered",
        "installation_id": plan["installation_id"],
        "digest": plan["sha256"],
        "request_id": "report-1",
    }
    response = rpc(client, token["access_token"], "report_install_result", report)
    assert response["structuredContent"]["data"]["source"] == "agent_reported"
    assert rpc(client, token["access_token"], "report_install_result", report)["structuredContent"]["ok"]
    bad = {**report, "request_id": None, "digest": "0" * 64}
    assert (
        rpc(client, token["access_token"], "report_install_result", bad)["structuredContent"]["error"]["code"]
        == "DIGEST_MISMATCH"
    )
    update = rpc(client, token["access_token"], "update_skill", {"installation_id": plan["installation_id"]})[
        "structuredContent"
    ]["data"]
    assert update["operation"] == "update" and update["expected_local_manifest"] == plan["manifest"]
    uninstall = rpc(
        client, token["access_token"], "uninstall_skill", {"installation_id": plan["installation_id"]}
    )["structuredContent"]["data"]
    assert uninstall["operation"] == "uninstall" and uninstall["manifest"] == plan["manifest"]
    assert rpc(
        client,
        token["access_token"],
        "report_install_result",
        {
            **report,
            "request_id": None,
            "installation_id": uninstall["installation_id"],
            "operation": "uninstall",
            "status": "uninstalled",
        },
    )["structuredContent"]["ok"]
    second = authorize(client, "lisi")
    assert rpc(client, second["access_token"], "list_installed_skills")["structuredContent"]["data"] == []
    assert rpc(
        client, second["access_token"], "uninstall_skill", {"installation_id": plan["installation_id"]}
    )["isError"]


def test_concurrent_name_claim_and_atomic_ticket(app):
    hub = app.state.hub

    def create(_):
        try:
            hub.run(
                "user-zhangsan",
                "upload_skill",
                {"team_id": "team-dev-a", "skill_md": skill_md("unique-helper")},
            )
            return "created"
        except HubError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sorted(pool.map(create, range(4))).count("created") == 1
    plan = hub.run("user-zhangsan", "create_download", {"skill_id": "git-commit-guide"})
    ticket = plan["download_url"].rsplit("/", 1)[1]

    def download(_):
        try:
            hub.redeem_download(ticket)
            return True
        except HubError:
            return False

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(download, range(4))) == 1


def test_redo_journal_recovers_cross_file_commit_once(tmp_path):
    root = tmp_path / "storage"
    Repository(root)
    event = {"event_id": "event-crash", "action": "publish", "actor": "test", "time": "test"}
    atomic_write(
        root / ".journal.json",
        json.dumps(
            {
                "writes": {
                    "skills": {"one": {"current_version": "1.0.0"}},
                    "versions": {"one@1.0.0": {"status": "published"}},
                },
                "events": [event],
            }
        ).encode(),
    )
    recovered = Repository(root)
    assert recovered.snapshot()["skills"]["one"]["current_version"] == "1.0.0"
    assert recovered.snapshot()["versions"]["one@1.0.0"]["status"] == "published"
    assert len(recovered.audit_events()) == 1
    atomic_write(root / ".journal.json", json.dumps({"writes": {}, "events": [event]}).encode())
    assert len(Repository(root).audit_events()) == 1


def test_idempotency_and_audit_redaction(client, app):
    login(client)
    assert upload(client, request_id="create-once").status_code == 200
    assert upload(client, request_id="create-once").status_code == 200
    assert upload(client, request_id="create-once", version="0.2.0").status_code == 409
    plan = api_post(
        client, "/installations/plan", {"skill_id": "git-commit-guide", "client": "codex"}
    ).json()["data"]
    assert client.get(plan["package"]["download_url"]).status_code == 200
    logs = (app.state.hub.settings.data_dir / "audit.ndjson").read_text()
    for secret in [
        "ZhangSan@123456",
        "Admin@123456",
        plan["package"]["download_url"].rsplit("/", 1)[1],
        client.cookies["skillhub_session"],
    ]:
        assert secret not in logs


def test_request_trace_correlates_response_and_audit(client, app):
    login(client)
    response = client.get("/api/v1/skills")
    trace_id = response.headers["x-request-id"]
    assert response.json()["trace_id"] == trace_id
    assert app.state.hub.repo.audit_events()[-1]["request_id"] == trace_id


def test_password_reset_revokes_pending_transfer_tickets(client):
    login(client)
    transfer = api_post(client, "/skills/git-commit-guide/download", {"version": "1.0.0"}).json()["data"]
    login(client, "admin")
    api_post(client, "/admin/users/user-zhangsan/password", {"password": "Changed@123456"})
    assert client.get(transfer["download_url"]).status_code == 410

from io import BytesIO
import zipfile

from conftest import api_post, authorize, rpc, skill_md
from backend.app.security.packages import digest


def test_remaining_mcp_mutation_contracts(client):
    user = authorize(client)["access_token"]

    def call(name, args):
        result = rpc(client, user, name, args)
        assert not result.get("isError"), (name, result)
        return result["structuredContent"]["data"]

    assert call("add_favorite", {"skill_id": "git-commit-guide"})["favorite"]
    assert not call("remove_favorite", {"skill_id": "git-commit-guide"})["favorite"]
    call("upload_skill", {"team_id": "team-dev-a", "skill_md": skill_md("tool-helper")})
    review = call("request_skill_review", {"skill_id": "tool-helper", "version": "0.1.0"})
    assert call("get_skill_review_status", {"review_id": review["review_id"]})["decision"] == "pending"
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("SKILL.md", skill_md("tool-zip-helper"))
    content = stream.getvalue()
    session = call(
        "prepare_skill_upload",
        {"team_id": "team-dev-a", "filename": "helper.zip", "size": len(content), "sha256": digest(content)},
    )
    assert client.post(session["upload_url"], content=content).status_code == 200
    assert (
        call("upload_skill", {"team_id": "team-dev-a", "upload_id": session["upload_id"]})["status"]
        == "draft"
    )
    manager = authorize(client, "admin")["access_token"]
    assert (
        api_post(
            client, "/reviews/" + review["review_id"] + "/decision", {"decision": "approved"}
        ).status_code
        == 200
    )
    for name in ["add_skill_to_collection", "remove_skill_from_collection"]:
        result = rpc(client, manager, name, {"collection_id": "col-dev-a", "skill_id": "mcp-tool-checklist"})
        assert not result["isError"]
    assert (
        call(
            "share_skill",
            {"skill_id": "tool-helper", "visibility": "custom", "acl": [{"type": "user", "id": "user-lisi"}]},
        )["decision"]
        == "pending"
    )
    assert call("rate_skill", {"skill_id": "tool-helper", "version": "0.1.0", "score": 5})["score"] == 5
    assert (
        call("report_skill_issue", {"skill_id": "tool-helper", "description": "Add one more example."})[
            "status"
        ]
        == "open"
    )

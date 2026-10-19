from pathlib import Path
from tempfile import TemporaryDirectory
import json
import os
import subprocess
import sys

from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app
from backend.app.seed import seed


def test_development_origin_is_opt_in_and_still_checks_csrf():
    for mode, expected in [("local-demo", 403), ("development", 200)]:
        with TemporaryDirectory() as folder:
            app = create_app(Settings(data_dir=Path(folder), app_env=mode))
            with TestClient(app, base_url="http://127.0.0.1:8765") as client:
                response = client.post(
                    "/api/v1/auth/login",
                    json={"username": "zhangsan", "password": "ZhangSan@123456"},
                    headers={"origin": "http://127.0.0.1:5180"},
                )
                assert response.status_code == expected
                if expected == 200:
                    assert (
                        client.post(
                            "/api/v1/favorites",
                            json={"skill_id": "git-commit-guide"},
                            headers={"origin": "http://127.0.0.1:5180"},
                        ).status_code
                        == 403
                    )


def test_seed_does_not_restore_removed_favorites_or_overwrite_changes(app):
    hub = app.state.hub
    with hub.repo.transaction() as tx:
        tx["favorites"].clear()
        tx["users"]["user-zhangsan"]["display_name"] = "已修改"
    seed(hub)
    snapshot = hub.repo.snapshot()
    assert snapshot["favorites"] == {}
    assert snapshot["users"]["user-zhangsan"]["display_name"] == "已修改"


def test_reset_requires_confirmation_and_preserves_backup(app):
    folder = app.state.hub.settings.data_dir
    with app.state.hub.repo.transaction() as tx:
        tx["users"]["user-zhangsan"]["display_name"] = "备份前的修改"
    before = (folder / "users.json").read_bytes()
    environment = {**os.environ, "DATA_DIR": str(folder)}
    rejected = subprocess.run(
        [sys.executable, "-m", "scripts.reset_demo", "--confirm", "NO"],
        env=environment,
        capture_output=True,
        text=True,
    )
    assert rejected.returncode != 0 and (folder / "users.json").read_bytes() == before
    accepted = subprocess.run(
        [sys.executable, "-m", "scripts.reset_demo", "--confirm", "RESET LOCAL DEMO"],
        env=environment,
        capture_output=True,
        text=True,
    )
    assert accepted.returncode == 0
    backups = list(folder.parent.glob("data-backup-*"))
    assert len(backups) == 1
    assert (
        json.loads((backups[0] / "users.json").read_text())["user-zhangsan"]["display_name"] == "备份前的修改"
    )
    assert json.loads((folder / "users.json").read_text())["user-zhangsan"]["display_name"] == "张三"

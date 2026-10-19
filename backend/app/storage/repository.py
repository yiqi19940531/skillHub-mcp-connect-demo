"""Single-writer JSON repository with a durable redo journal and append-only audit export."""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
import uuid

from filelock import FileLock
from backend.app.errors import TRACE_ID

TABLES = (
    "users",
    "teams",
    "memberships",
    "categories",
    "skills",
    "versions",
    "collections",
    "favorites",
    "reviews",
    "share_requests",
    "ratings",
    "issues",
    "installations",
    "uploads",
    "tickets",
    "sessions",
    "oauth_clients",
    "oauth_requests",
    "oauth_codes",
    "oauth_grants",
    "oauth_refresh",
    "idempotency",
    "usage_events",
)


def now():
    return datetime.now(timezone.utc).isoformat()


def uid(prefix):
    return prefix + "-" + uuid.uuid4().hex


def sync_directory(path: Path):
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_write(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("." + path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with open(temporary, "xb") as stream:
            os.chmod(temporary, 0o600)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        sync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


class Transaction:
    def __init__(self, tables):
        self.tables = tables
        self.events = []

    def __getitem__(self, table):
        return self.tables[table]

    def audit(self, actor, action, target=None, result="success", decision="allow", **safe_details):
        self.events.append(
            {
                "event_id": uid("evt"),
                "request_id": TRACE_ID.get() or uid("req"),
                "actor": actor,
                "action": action,
                "target": target,
                "decision": decision,
                "result": result,
                "time": now(),
                "details": safe_details,
            }
        )


class Repository:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        os.chmod(root, 0o700)
        self.mutex = threading.RLock()
        self.file_lock = FileLock(str(root / ".write.lock"))
        with self.mutex, self.file_lock:
            self._recover()

    def path(self, table):
        assert table in TABLES
        folder = self.root / "oauth" if table.startswith("oauth_") else self.root
        return folder / (table + ".json")

    def _load(self):
        return {
            name: json.loads(self.path(name).read_text()) if self.path(name).exists() else {}
            for name in TABLES
        }

    def _recover(self):
        journal_path = self.root / ".journal.json"
        if not journal_path.exists():
            return
        journal = json.loads(journal_path.read_text())
        for name, value in journal["writes"].items():
            atomic_write(self.path(name), json.dumps(value, ensure_ascii=False, indent=2).encode())
        audit_path = self.root / "audit.ndjson"
        # A crash may leave a partial final audit line. Drop only that incomplete suffix.
        existing = audit_path.read_bytes() if audit_path.exists() else b""
        if existing and not existing.endswith(b"\n"):
            existing = existing[: existing.rfind(b"\n") + 1]
            atomic_write(audit_path, existing)
        seen = {json.loads(line)["event_id"] for line in existing.splitlines() if line}
        with open(audit_path, "ab") as stream:
            os.chmod(audit_path, 0o600)
            for event in journal["events"]:
                if event["event_id"] not in seen:
                    stream.write(json.dumps(event, ensure_ascii=False).encode() + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        journal_path.unlink()
        sync_directory(self.root)

    @contextmanager
    def transaction(self):
        with self.mutex, self.file_lock:
            self._recover()
            tables = self._load()
            original = {key: json.dumps(value, sort_keys=True) for key, value in tables.items()}
            tx = Transaction(tables)
            yield tx
            writes = {
                key: value
                for key, value in tables.items()
                if json.dumps(value, sort_keys=True) != original[key]
            }
            if writes or tx.events:
                atomic_write(
                    self.root / ".journal.json",
                    json.dumps({"writes": writes, "events": tx.events}, ensure_ascii=False).encode(),
                )
                self._recover()

    def snapshot(self):
        with self.transaction() as tx:
            return tx.tables

    def audit_events(self):
        with self.mutex, self.file_lock:
            self._recover()
            path = self.root / "audit.ndjson"
            return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

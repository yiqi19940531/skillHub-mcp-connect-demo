from dataclasses import dataclass, field
import os
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]


def load_local_environment():
    """Read literal KEY=VALUE settings without executing shell commands."""
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text().splitlines():
            key, separator, value = line.strip().partition("=")
            if separator and (
                key.startswith(("APP_", "OAUTH_", "SESSION_", "TRANSFER_", "MAX_"))
                or key in {"DATA_DIR", "DEMO_SEED_ENABLED", "DEV_FRONTEND_ORIGIN"}
            ):
                os.environ.setdefault(key, value.strip().strip("\"'"))


load_local_environment()


@dataclass(frozen=True)
class Settings:
    app_env: str = field(default_factory=lambda: os.getenv("APP_ENV", "local-demo"))
    dev_frontend_origin: str = field(
        default_factory=lambda: os.getenv("DEV_FRONTEND_ORIGIN", "http://127.0.0.1:5180")
    )
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("DATA_DIR", str(ROOT / "data"))).resolve())
    base_url: str = field(
        default_factory=lambda: os.getenv("APP_BASE_URL", "http://127.0.0.1:8765").rstrip("/")
    )
    seed_enabled: bool = field(
        default_factory=lambda: os.getenv("DEMO_SEED_ENABLED", "true").lower() == "true"
    )
    session_minutes: int = field(default_factory=lambda: int(os.getenv("SESSION_TTL_MINUTES", "120")))
    access_minutes: int = field(
        default_factory=lambda: int(os.getenv("OAUTH_ACCESS_TOKEN_TTL_MINUTES", "30"))
    )
    refresh_days: int = field(default_factory=lambda: int(os.getenv("OAUTH_REFRESH_TOKEN_TTL_DAYS", "7")))
    ticket_seconds: int = field(default_factory=lambda: int(os.getenv("TRANSFER_TICKET_TTL_SECONDS", "120")))
    max_zip: int = field(default_factory=lambda: int(os.getenv("MAX_UPLOAD_ZIP_BYTES", "2097152")))
    max_expanded: int = field(default_factory=lambda: int(os.getenv("MAX_UNCOMPRESSED_BYTES", "10485760")))
    max_files: int = field(default_factory=lambda: int(os.getenv("MAX_UPLOAD_FILES", "100")))

    @property
    def resource(self) -> str:
        return self.base_url + "/mcp"

    def validate(self):
        url = urlsplit(self.base_url)
        if url.scheme != "http" or url.hostname not in {"127.0.0.1", "localhost", "::1"} or url.path:
            raise ValueError("本机 PoC 的 APP_BASE_URL 必须是无路径的 HTTP loopback 地址")
        dev = urlsplit(self.dev_frontend_origin)
        if dev.scheme != "http" or dev.hostname not in {"127.0.0.1", "localhost", "::1"} or dev.path:
            raise ValueError("DEV_FRONTEND_ORIGIN 必须是无路径的 HTTP loopback 地址")

    @property
    def web_origins(self):
        origins = {None, self.base_url}
        if self.app_env == "development":
            origins.add(self.dev_frontend_origin)
        return origins

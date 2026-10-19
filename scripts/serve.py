import os

import uvicorn

from backend.app.config import Settings


def main():
    cfg = Settings()
    cfg.validate()
    host = os.getenv("APP_HOST", "127.0.0.1")
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("本机 PoC 只允许 loopback 监听地址")
    uvicorn.run(
        "backend.app.main:app_factory",
        factory=True,
        host=host,
        port=int(os.getenv("APP_PORT", "8765")),
        workers=1,
        access_log=False,
    )


if __name__ == "__main__":
    main()

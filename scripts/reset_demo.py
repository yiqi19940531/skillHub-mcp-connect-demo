import argparse
from datetime import datetime, timezone
import os
from pathlib import Path

from filelock import FileLock, Timeout

from backend.app.config import ROOT, Settings
from backend.app.seed import seed
from backend.app.services.hub import Hub


def main():
    parser = argparse.ArgumentParser(description="备份当前本机演示数据后重建；必须显式确认")
    parser.add_argument("--confirm", help='输入精确文字 "RESET LOCAL DEMO"')
    args = parser.parse_args()
    cfg = Settings()
    folder = cfg.data_dir
    if not folder.exists() or not (folder / ".seeded").is_file() or folder in {ROOT, Path.home(), Path("/")}:
        raise SystemExit("拒绝重置：目标不是已初始化的 Skill Hub 演示数据目录")
    confirmation = args.confirm or input(f"将备份并重建 {folder}。请输入 RESET LOCAL DEMO：")
    if confirmation != "RESET LOCAL DEMO":
        raise SystemExit("未确认，不更改数据")
    lock = FileLock(str(folder / ".server.lock"))
    try:
        lock.acquire(timeout=0)
    except Timeout as exc:
        raise SystemExit("请先停止 Skill Hub 服务再重置") from exc
    try:
        backup = folder.with_name(
            folder.name + "-backup-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        )
        os.replace(folder, backup)
        seed(Hub(cfg))
        print(f"已重建；完整旧数据保留于 {backup}。该备份含本机密钥和授权记录，请妥善保管。")
    finally:
        lock.release()


if __name__ == "__main__":
    main()

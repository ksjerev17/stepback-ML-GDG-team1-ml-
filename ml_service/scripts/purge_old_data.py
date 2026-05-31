# 출처: CLAUDE.md §13.6, §16.3
"""90일 지난 audit log + feedback row 삭제."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import LOGS_DIR  # noqa: E402
from app.core.feedback_store import purge_older_than  # noqa: E402


def purge_audit_logs(days: int = 90) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    deleted = 0
    if not LOGS_DIR.exists():
        return 0
    for f in LOGS_DIR.glob("audit-*.jsonl"):
        try:
            stat = f.stat()
            ts = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        except OSError:
            continue
        if ts < cutoff:
            try:
                f.unlink()
                deleted += 1
            except OSError:
                pass
    return deleted


def main() -> int:
    db_rows = purge_older_than(days=90)
    log_files = purge_audit_logs(days=90)
    print(f"[purge] feedback rows deleted: {db_rows}")
    print(f"[purge] audit log files deleted: {log_files}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

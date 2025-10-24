"""Perform placeholder database migrations."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

STATE_DIR = Path("/opt/watchmysix/state")
STATE_DIR.mkdir(parents=True, exist_ok=True)
MIGRATION_LOG = STATE_DIR / "migrations.json"


def main() -> None:
    record = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "status": "noop",
        "message": "No database configured; recorded migration checkpoint.",
    }

    history = []
    if MIGRATION_LOG.exists():
        history = json.loads(MIGRATION_LOG.read_text())

    history.append(record)
    MIGRATION_LOG.write_text(json.dumps(history, indent=2))
    print(f"Recorded migration checkpoint at {record['timestamp']}")


if __name__ == "__main__":
    main()

"""Expire only recognized local backup directories. Dry run unless --apply.

The independent erasure ledger must never live within this backup root.
"""

import argparse
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path


def prune(root, days, apply=False, now=None):
    if not 1 <= days <= 3650:
        raise ValueError("Retenção deve ser de 1 a 3650 dias.")
    root = Path(root).resolve()
    if not root.is_dir() or root == Path("/"):
        raise ValueError("Informe uma raiz de backups existente.")
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=days)
    expired = []
    for directory in sorted(root.iterdir()):
        if directory.is_symlink() or not directory.is_dir():
            continue
        # Refuse any extra file or nested directory, including an erasure ledger.
        entries = set(path.name for path in directory.iterdir())
        if entries != {"database.dump", "files.zip", "manifest.json"}:
            continue
        if any(path.is_symlink() or not path.is_file() for path in directory.iterdir()):
            continue
        try:
            manifest = json.loads((directory / "manifest.json").read_text())
            created = datetime.fromisoformat(manifest["created_at"])
            if manifest["version"] != 1 or created.tzinfo is None or created >= cutoff:
                continue
        except (ValueError, KeyError, TypeError):
            continue
        expired.append(directory.name)
        if apply:
            shutil.rmtree(directory)
    return {"expired": expired, "apply": apply, "retention_days": days}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root")
    parser.add_argument("--retention-days", required=True, type=int)
    parser.add_argument("--apply", action="store_true")
    options = parser.parse_args()
    print(json.dumps(prune(options.root, options.retention_days, options.apply)))

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from django.test import SimpleTestCase
from scripts.prune_backups import prune


class BackupRetentionTests(SimpleTestCase):
    def test_preview_and_expiration_preserve_recent_unknown_and_ledger_directories(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            now = datetime.now(timezone.utc)
            for name, age in [("old", 40), ("recent", 2), ("with-ledger", 40)]:
                backup = root / name
                backup.mkdir()
                (backup / "database.dump").write_bytes(b"synthetic")
                (backup / "files.zip").write_bytes(b"synthetic")
                (backup / "manifest.json").write_text(
                    json.dumps(
                        {
                            "version": 1,
                            "created_at": (now - timedelta(days=age)).isoformat(),
                        }
                    )
                )
            (root / "with-ledger" / "tombstone.json").write_text("{}")
            (root / "unknown").mkdir()
            (root / "symlink").symlink_to(root / "old", target_is_directory=True)
            self.assertEqual(prune(root, 30, now=now)["expired"], ["old"])
            self.assertTrue((root / "old").exists())
            prune(root, 30, apply=True, now=now)
            self.assertFalse((root / "old").exists())
            self.assertTrue((root / "recent").exists())
            self.assertTrue((root / "with-ledger").exists())
            self.assertTrue((root / "unknown").exists())
            with self.assertRaises(ValueError):
                prune(root, 0)

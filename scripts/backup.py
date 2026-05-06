#!/usr/bin/env python3
"""Daily backup cron script. Runs at 1:15 AM inside backend container.
Copies /data/kennel.db to /mnt/nas/kennel_db_YYYY-MM-DD.sqlite.
Prunes backups older than backup_retention_days from system.json.
"""

import json
import os
import shutil
import sys
from datetime import datetime, timedelta

CONFIG_DIR = os.environ.get("CONFIG_DIR", "/config")
DB_PATH = os.environ.get("DB_PATH", "/data/kennel.db")


def main():
    with open(os.path.join(CONFIG_DIR, "system.json")) as f:
        system = json.load(f)

    backup_path = system["backup_path"]
    retention_days = int(system["backup_retention_days"])
    today = datetime.now().strftime("%Y-%m-%d")
    dest = os.path.join(backup_path, f"kennel_db_{today}.sqlite")

    os.makedirs(backup_path, exist_ok=True)
    shutil.copy2(DB_PATH, dest)
    print(f"Backup written: {dest}", flush=True)

    # Prune old backups
    cutoff = datetime.now() - timedelta(days=retention_days)
    for filename in os.listdir(backup_path):
        if not filename.startswith("kennel_db_") or not filename.endswith(".sqlite"):
            continue
        date_str = filename[len("kennel_db_"):-len(".sqlite")]
        try:
            file_date = datetime.strptime(date_str, "%Y-%m-%d")
            if file_date < cutoff:
                os.remove(os.path.join(backup_path, filename))
                print(f"Pruned: {filename}", flush=True)
        except ValueError:
            pass


if __name__ == "__main__":
    main()

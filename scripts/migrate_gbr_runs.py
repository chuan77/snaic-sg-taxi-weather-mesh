#!/usr/bin/env python3
"""
One-shot migration: move FINISHED gbr_* runs from Default (exp=0)
to sg-taxi-demand-forecast (exp=1), soft-delete all FAILED gbr_* runs.

STOP the MLflow server before running this script.
Run from project root: uv run python scripts/migrate_gbr_runs.py
"""
import sqlite3
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DB           = PROJECT_ROOT / "data" / "mlflow.db"
MLRUNS       = PROJECT_ROOT / "data" / "mlruns"


def main() -> None:
    conn = sqlite3.connect(str(DB))
    cur  = conn.cursor()

    # 1. Move FINISHED gbr_* runs from Default (0) → sg-taxi-demand-forecast (1)
    cur.execute("""
        SELECT run_uuid, artifact_uri FROM runs
        WHERE experiment_id = 0 AND name LIKE 'gbr_%' AND status = 'FINISHED'
    """)
    finished = cur.fetchall()

    moved = 0
    for run_uuid, artifact_uri in finished:
        src = MLRUNS / "0" / run_uuid
        dst = MLRUNS / "1" / run_uuid
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
        new_uri = artifact_uri.replace("/mlruns/0/", "/mlruns/1/")
        cur.execute(
            "UPDATE runs SET experiment_id = 1, artifact_uri = ? WHERE run_uuid = ?",
            (new_uri, run_uuid),
        )
        moved += 1

    # 2. Soft-delete all FAILED gbr_* runs in both experiments
    cur.execute("""
        UPDATE runs SET lifecycle_stage = 'deleted'
        WHERE name LIKE 'gbr_%' AND status = 'FAILED'
    """)
    deleted = cur.rowcount

    conn.commit()
    conn.close()

    print(f"Moved   {moved} FINISHED runs  → sg-taxi-demand-forecast (exp=1)")
    print(f"Deleted {deleted} FAILED runs  (soft-delete, reversible via lifecycle_stage='active')")


if __name__ == "__main__":
    main()

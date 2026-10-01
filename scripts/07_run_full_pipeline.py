#!/usr/bin/env python3
"""Run each required phase in order and stop at the first failed phase."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEPS = [
    "scripts/00_audit_data.py",
    "scripts/01_build_datasets.py",
    "scripts/02_train_recipe_chemistry.py",
    "scripts/03_train_chemistry_sensory.py",
    "scripts/04_train_recipe_sensory.py",
    "scripts/05_build_optimizer.py",
    "scripts/06_generate_report.py",
]


def main():
    for script in STEPS:
        print(f"[PIPELINE] {script}", flush=True)
        result = subprocess.run([sys.executable, str(ROOT / script)], cwd=ROOT)
        if result.returncode:
            raise SystemExit(f"Pipeline stopped at {script} with exit code {result.returncode}")
    print("[PIPELINE] PASS: all required phases completed")


if __name__ == "__main__":
    main()


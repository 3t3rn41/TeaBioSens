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
    "scripts/09_validate_recipe_sensory_association.py",
    "scripts/10_sensory_noise_decomposition.py",
    "scripts/08_validate_gate_b.py",
    "scripts/06_generate_report.py",
]


def main():
    for script in STEPS:
        print(f"[PIPELINE] {script}", flush=True)
        command = [sys.executable, str(ROOT / script)]
        if script == "scripts/08_validate_gate_b.py":
            command.extend(["--permutations", "200", "--seed", "42", "--n-jobs", "7"])
        result = subprocess.run(command, cwd=ROOT)
        if result.returncode:
            raise SystemExit(f"Pipeline stopped at {script} with exit code {result.returncode}")
        if script == "scripts/08_validate_gate_b.py":
            print("[PIPELINE] rebuilding recommendations with the current Gate B permutation result", flush=True)
            result = subprocess.run([sys.executable, str(ROOT / "scripts/05_build_optimizer.py")], cwd=ROOT)
            if result.returncode:
                raise SystemExit("Pipeline stopped while rebuilding recommendations after Gate B")
        if script == "scripts/01_build_datasets.py":
            print("[PIPELINE] running dataset, feature, ratio, leakage and design-space acceptance checks", flush=True)
            result = subprocess.run([
                sys.executable, "-m", "pytest", "-q",
                "tests/test_dataset_contract.py", "tests/test_no_leakage.py",
                "tests/test_features.py", "tests/test_ratios.py", "tests/test_design_space.py",
            ], cwd=ROOT)
            if result.returncode:
                raise SystemExit("Dataset acceptance checks failed")
    print("[PIPELINE] scripts complete; running project test suite", flush=True)
    result = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT)
    if result.returncode:
        raise SystemExit(f"Pipeline acceptance tests failed with exit code {result.returncode}")
    print("[PIPELINE] PASS: all required phases and acceptance tests completed")


if __name__ == "__main__":
    main()

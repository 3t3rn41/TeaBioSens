from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def phase(name: str, status: str, input_text: str, output_text: str, metrics: str = "", warnings: str = "", next_text: str = ""):
    print(f"[PHASE] {name}")
    print(f"[STATUS] {status}")
    print(f"[INPUT] {input_text}")
    print(f"[OUTPUT] {output_text}")
    if metrics:
        print(f"[KEY_METRICS] {metrics}")
    print(f"[WARNINGS] {warnings or 'none'}")
    print(f"[NEXT] {next_text or 'complete'}")


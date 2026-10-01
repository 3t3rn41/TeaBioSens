#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from _common import ROOT, phase
from tea_ai.io import read_source
from tea_ai.preprocessing import build_datasets


def main():
    parser = argparse.ArgumentParser(description="Build clean and modeling datasets")
    parser.add_argument("--input", default=str(ROOT / "data/raw/TeaBioSens.xlsx"))
    parser.add_argument("--output-dir", default=str(ROOT / "data/processed"))
    args = parser.parse_args()
    frame = read_source(args.input)
    paths = build_datasets(frame, args.input, args.output_dir)
    phase("M1 build datasets", "PASS", args.input, ", ".join(str(path) for path in paths.values()), "blend_master=30 rows; sensory_observations=597 rows; design points=32")


if __name__ == "__main__":
    main()


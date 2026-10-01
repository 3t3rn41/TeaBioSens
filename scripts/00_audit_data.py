#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from _common import ROOT, phase
from tea_ai.io import read_source, sha256_file, write_json
from tea_ai.validation import audit_dataframe


def main():
    parser = argparse.ArgumentParser(description="Audit the immutable TeaBioSens source workbook")
    parser.add_argument("--input", default=str(ROOT / "data/raw/TeaBioSens.xlsx"))
    parser.add_argument("--sheet", default="Sheet1")
    args = parser.parse_args()
    input_path = Path(args.input)
    frame = read_source(input_path, sheet_name=args.sheet)
    report = audit_dataframe(frame, sheet_name=args.sheet)
    report["input_file"] = str(input_path)
    report["input_sha256"] = sha256_file(input_path)
    output_dir = ROOT / "artifacts/reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "data_audit.json", report)
    lines = ["# TeaBioSens raw data audit", "", f"**Status:** {report['status']}", "", "## Contract", "", f"- Sheet: `{report['sheet']}`", f"- Rows including header: {report['rows_with_header']}", f"- Observations: {report['data_rows']}", f"- Columns: {report['columns']}", f"- Unique blends: {report['unique_sample_codes']}", f"- Missing values: {report['missing_values']}", f"- Exact duplicate rating rows retained: {report['exact_duplicate_rows']}", f"- Source SHA256: `{report['input_sha256']}`", "", "## Discrete design space", ""]
    design = report.get("design_space") or {}
    lines.extend([f"- Legal design points enumerated: {design.get('valid_point_count')}", f"- Observed design points: {design.get('observed_point_count')}", f"- Current coverage: {design.get('coverage', 0):.2%}", f"- Unobserved legal points (g): `{design.get('unobserved_points_g')}`", "", "## Sensory summary", "", "| Metric | Min | Max | Mean |", "|---|---:|---:|---:|"])
    for target, stats in report.get("sensory_summary", {}).items():
        lines.append(f"| {target} | {stats['min']:.3f} | {stats['max']:.3f} | {stats['mean']:.3f} |")
    lines.extend(["", "## Findings", ""])
    lines.extend([f"- ERROR: {item}" for item in report.get("errors", [])] or ["- No contract errors."])
    lines.extend([f"- WARNING: {item}" for item in report.get("warnings", [])])
    (output_dir / "data_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    phase("M0 data audit", report["status"], str(input_path), "artifacts/reports/data_audit.json, data_audit.md", f"597 rows; 30 blends; design coverage={design.get('coverage', 0):.2%}", "; ".join(report.get("warnings", [])), "M1 build datasets")
    if report["errors"]:
        raise SystemExit("Data audit failed: " + "; ".join(report["errors"]))


if __name__ == "__main__":
    main()


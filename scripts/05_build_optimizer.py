#!/usr/bin/env python3
from _common import phase
from tea_ai.optimization import rank_design_space


def main():
    result = rank_design_space()
    summary = result["summary"]
    phase("M6 design-space ranker", "PASS", "32 legal discrete recipe points", "artifacts/optimization/design_space_32.csv, next_experiments.csv, top_candidates.csv", f"coverage={summary['coverage']:.2%}; top candidates={summary['top_k_returned']}; eligible points={summary['eligible_count']}", summary["scientific_note"], "M7 explanations and M8 Demo")


if __name__ == "__main__":
    main()


#!/usr/bin/env python3
from _common import phase
from tea_ai.models.training import train_recipe_chemistry


def main():
    metrics = train_recipe_chemistry()
    phase("M3 Recipe -> Chemistry", "PASS_WITH_WARNINGS" if metrics["gate"]["status"] == "FAIL" else "PASS", "blend_master.csv (30 recipes)", "chemistry model, OOF predictions, metrics and report", f"improved targets={metrics['gate']['improved_targets']}; CV=LOO within-design reconstruction", "some targets may not beat mean baseline; see report", "M4 Chemistry -> Sensory")


if __name__ == "__main__":
    main()


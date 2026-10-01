#!/usr/bin/env python3
from _common import phase
from tea_ai.models.training import train_chemistry_sensory


def main():
    metrics = train_chemistry_sensory()
    phase("M4 Chemistry -> Sensory", "PASS_WITH_WARNINGS" if metrics["gate"]["status"] == "FAIL" else "PASS", "sensory_observations.csv (597 ratings; 30 groups)", "sensory model, grouped OOF predictions and reports", f"improved blend-mean targets={metrics['gate']['improved_targets']}; CV=LeaveOneGroupOut", "597 ratings are not 597 independent blends", "M5 Recipe -> Sensory")


if __name__ == "__main__":
    main()


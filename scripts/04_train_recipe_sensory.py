#!/usr/bin/env python3
from _common import phase
from tea_ai.models.training import train_direct_recipe_sensory


def main():
    metrics = train_direct_recipe_sensory()
    phase("M5 Recipe -> Sensory", "PASS_WITH_WARNINGS" if metrics["gate"]["status"] == "FAIL" else "PASS", "blend_master.csv (30 recipes)", "direct sensory model, OOF predictions and report", f"overall-score MAE={metrics['by_target']['overall_score']['selected_metrics']['mae']:.4f}; mean baseline MAE={metrics['by_target']['overall_score']['baseline']['mae']:.4f}; gate={metrics['gate']['status']}", "within-design reconstruction only", "M6 discrete design ranker")


if __name__ == "__main__":
    main()


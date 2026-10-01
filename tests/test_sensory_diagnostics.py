import numpy as np
import pandas as pd
import pytest

from tea_ai.association import mantel_recipe_sensory_test
from tea_ai.constants import MODEL_SENSORY_TARGETS, RECIPE_FEATURES, SENSORY_TARGETS
from tea_ai.diagnostics import sensory_noise_decomposition
from tea_ai.models.direct_recipe import recipe_targets
from tea_ai.optimization import _objective


def test_solubility_remains_measured_but_is_not_a_model_target():
    assert "solubility" in SENSORY_TARGETS
    assert "solubility" not in MODEL_SENSORY_TARGETS
    assert recipe_targets() == MODEL_SENSORY_TARGETS
    with pytest.raises(ValueError, match="descriptive-only"):
        _objective({"solubility": 50.0}, "weighted_sensory", {"solubility": 1.0})


def test_noise_decomposition_recovers_balanced_one_way_components():
    observations = pd.DataFrame({
        "sample_code": ["A", "A", "B", "B", "C", "C"],
        "overall_score": [0.0, 2.0, 10.0, 12.0, 20.0, 22.0],
    })
    result = sensory_noise_decomposition(observations, targets=["overall_score"])
    outcome = result["targets"]["overall_score"]
    assert outcome["between_recipe_variance"] == pytest.approx(99.0)
    assert outcome["within_recipe_rating_variance"] == pytest.approx(2.0)
    assert outcome["between_recipe_variance_share"] == pytest.approx(99 / 101)
    assert outcome["mean_of_recipe_mean_reliability"] == pytest.approx(0.99)


def test_mantel_test_is_reproducible_and_uses_jointly_modeled_outcomes():
    X = np.array([
        [0.4, 0.3, 0.2, 0.1], [0.1, 0.4, 0.3, 0.2],
        [0.2, 0.1, 0.4, 0.3], [0.3, 0.2, 0.1, 0.4],
        [0.4, 0.2, 0.1, 0.3], [0.1, 0.3, 0.2, 0.4],
    ])
    frame = pd.DataFrame(X, columns=RECIPE_FEATURES)
    for index, target in enumerate(MODEL_SENSORY_TARGETS):
        frame[f"{target}_mean"] = X[:, index % 4] + 0.05 * X[:, (index + 1) % 4]
    first = mantel_recipe_sensory_test(frame, permutations=49, seed=7)
    second = mantel_recipe_sensory_test(frame, permutations=49, seed=7)
    assert first == second
    assert first["n_independent_recipes"] == len(frame)
    assert first["permutations"] == 49
    assert set(first["per_target_supplementary"]) == set(MODEL_SENSORY_TARGETS)
    assert 0 < first["global_multivariate"]["permutation_p_value"] <= 1

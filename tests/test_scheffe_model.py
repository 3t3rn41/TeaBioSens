import numpy as np

from tea_ai.constants import RECIPE_FEATURES
from tea_ai.models.mixture import scheffe_quadratic_estimator


def test_quadratic_scheffe_has_linear_and_pairwise_terms_without_intercept():
    X = np.array([
        [0.125, 0.125, 0.500, 0.250],
        [0.250, 0.250, 0.250, 0.250],
        [0.500, 0.125, 0.125, 0.250],
    ])
    model = scheffe_quadratic_estimator()
    terms = model.named_steps["scheffe_terms"].fit(X).get_feature_names_out(RECIPE_FEATURES)
    assert len(terms) == 10
    assert all("^2" not in name for name in terms)
    assert model.named_steps["ols"].fit_intercept is False


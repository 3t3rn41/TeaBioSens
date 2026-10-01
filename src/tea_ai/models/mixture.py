"""Models and feature maps for constrained mixture-design experiments."""

from __future__ import annotations

from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import PolynomialFeatures


def scheffe_quadratic_estimator() -> Pipeline:
    """Return the second-order Scheffé mixture model.

    For proportions that sum to one, the model is
    ``y = sum(beta_i * x_i) + sum(beta_ij * x_i * x_j)``.
    The interaction-only expansion omits squared terms and the estimator has
    no intercept, matching the standard quadratic Scheffé form. The expansion
    is learned as part of the estimator so callers can pass raw proportions.
    """
    return Pipeline([
        ("scheffe_terms", PolynomialFeatures(
            degree=2, interaction_only=True, include_bias=False,
        )),
        ("ols", LinearRegression(fit_intercept=False)),
    ])

"""Small-sample predictive spread estimates; these are not calibrated intervals."""

from __future__ import annotations

import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, Matern, WhiteKernel
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def gaussian_process(seed: int = 42) -> Pipeline:
    kernel = ConstantKernel(1.0, (1e-2, 1e2)) * Matern(length_scale=1.0, nu=1.5) + WhiteKernel(noise_level=0.1, noise_level_bounds=(1e-4, 1.0))
    return Pipeline([
        ("scale", StandardScaler()),
        ("gpr", GaussianProcessRegressor(kernel=kernel, normalize_y=True, n_restarts_optimizer=0, random_state=seed)),
    ])


def predict_mean_std(estimator, X) -> tuple[np.ndarray, np.ndarray]:
    model = estimator.named_steps.get("gpr") if hasattr(estimator, "named_steps") else estimator
    scaler = estimator.named_steps.get("scale") if hasattr(estimator, "named_steps") else None
    matrix = scaler.transform(X) if scaler is not None else X
    mean, std = model.predict(matrix, return_std=True)
    return np.asarray(mean).reshape(-1), np.asarray(std).reshape(-1)


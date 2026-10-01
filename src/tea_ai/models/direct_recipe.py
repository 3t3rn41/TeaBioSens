"""Direct recipe-to-sensory model task."""

from ..constants import MODEL_SENSORY_TARGETS, RECIPE_FEATURES
from .common import candidate_estimators


def recipe_features(frame):
    return frame[RECIPE_FEATURES]


def recipe_targets():
    return MODEL_SENSORY_TARGETS


def recipe_candidates(n_features=4):
    return candidate_estimators(n_features)

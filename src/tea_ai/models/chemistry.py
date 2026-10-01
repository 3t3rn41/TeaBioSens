"""Recipe-to-base-chemistry model task."""

from ..constants import CHEMISTRY_BASE, RECIPE_FEATURES
from .common import candidate_estimators


def chemistry_features(frame):
    return frame[RECIPE_FEATURES]


def chemistry_targets():
    return CHEMISTRY_BASE


def chemistry_candidates(n_features=4):
    return candidate_estimators(n_features)


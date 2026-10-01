"""Chemistry-to-sensory model task."""

from ..constants import CHEMISTRY_ALL, CHEMISTRY_BASE, SENSORY_TARGETS
from .common import candidate_estimators


def chemistry_feature_sets():
    return {"chemistry_a": CHEMISTRY_BASE, "chemistry_b": CHEMISTRY_ALL}


def sensory_targets():
    return SENSORY_TARGETS


def sensory_candidates(n_features):
    return candidate_estimators(n_features)


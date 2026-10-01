"""Leakage-aware grouped split helpers."""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np
from sklearn.model_selection import LeaveOneGroupOut, LeaveOneOut


def leave_one_group_out(groups) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    values = np.asarray(groups)
    splitter = LeaveOneGroupOut()
    for train, test in splitter.split(np.zeros(len(values)), groups=values):
        if set(values[train]).intersection(set(values[test])):
            raise AssertionError("CV leakage: sample_code appears in train and test")
        yield train, test


def leave_one_out(n_samples: int) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    for train, test in LeaveOneOut().split(np.arange(n_samples)):
        yield train, test


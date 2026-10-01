import numpy as np

from tea_ai.cv import leave_one_group_out


def test_leave_one_group_out_never_splits_a_blend():
    groups = np.repeat([f"S{i}" for i in range(30)], [20] * 29 + [17])
    folds = list(leave_one_group_out(groups))
    assert len(folds) == 30
    for train, test in folds:
        assert set(groups[train]).isdisjoint(set(groups[test]))
        assert len(set(groups[test])) == 1


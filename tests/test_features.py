import numpy as np
import pytest

from tea_ai.features import validate_composition, validate_recipe
from tea_ai.schema import recipe_schema_from_mapping


def test_compositional_recipe_contract():
    values = validate_recipe([0.125, 0.25, 0.5, 0.125])
    assert np.isclose(values.sum(), 1.0)
    for invalid in ([0.2, 0.2, 0.2, 0.2], [-0.1, 0.4, 0.4, 0.3], [np.nan, 0.2, 0.3, 0.5]):
        with pytest.raises(ValueError):
            validate_recipe(invalid)


def test_configurable_n_ingredient_schema_and_composition():
    schema = recipe_schema_from_mapping({
        "total_mass": 4.0,
        "ingredients": [
            {"key": key, "mass_column": f"{key}_g", "proportion_column": f"{key}_pct", "levels": [1.0, 2.0]}
            for key in ("a", "b", "c")
        ],
    })
    assert schema.n_ingredients == 3
    assert schema.enumerate_valid_points() == {(1.0, 1.0, 2.0), (1.0, 2.0, 1.0), (2.0, 1.0, 1.0)}
    assert np.allclose(validate_composition([0.25, 0.25, 0.5], ["a", "b", "c"]), [0.25, 0.25, 0.5])

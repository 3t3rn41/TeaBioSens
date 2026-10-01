import pandas as pd

from tea_ai.design_space import RecipeDesignSpace, enumerate_valid_design_points, extract_observed_recipe_points


def test_design_space_is_enumerated_and_missing_points_derived():
    master = pd.read_csv("data/processed/blend_master.csv")
    valid = enumerate_valid_design_points()
    observed = extract_observed_recipe_points(master)
    assert len(valid) == 32
    assert len(observed) == 30
    assert valid - observed == {
        (0.5, 1.0, 1.5, 1.0),
        (0.5, 1.5, 0.5, 1.5),
    }
    design = RecipeDesignSpace(master)
    assert design.describe()["coverage"] == 0.9375
    assert design.recipe_status([0.5, 1.0, 1.5, 1.0]) == "UNOBSERVED_VALID"
    assert design.recipe_status([0.7, 0.9, 1.2, 1.2]) == "INVALID_DESIGN_POINT"
    point = master.iloc[0][["green_g", "white_g", "oolong_g", "black_g"]].to_numpy()
    assert design.recipe_status(point) == "OBSERVED"


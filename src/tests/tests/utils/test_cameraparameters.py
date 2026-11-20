from photobooth.utils.cameraparameters import resolve_extreme_choice


def test_min_max_select_numeric_choice():
    apertures = ["3.5", "4", "5.6", "8", "22"]
    assert resolve_extreme_choice("min", apertures) == "3.5"
    assert resolve_extreme_choice("max", apertures) == "22"
    assert resolve_extreme_choice("min", ["Auto", "100", "200"]) == "100"
    assert resolve_extreme_choice("max", ["1/4000", "1/60", "1/30", "1", "bulb"]) == "1"


def test_other_values_unchanged():
    assert resolve_extreme_choice("5.6", ["4", "5.6"]) == "5.6"
    assert resolve_extreme_choice("min", ["Auto"]) == "min"

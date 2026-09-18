from temperature import fahrenheit_to_celsius


def test_freezing_point() -> None:
    assert fahrenheit_to_celsius(32) == 0


def test_boiling_point() -> None:
    assert fahrenheit_to_celsius(212) == 100


def test_negative_temperature() -> None:
    assert fahrenheit_to_celsius(-40) == -40
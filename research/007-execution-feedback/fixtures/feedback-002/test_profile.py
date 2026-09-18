from profile import display_name


def test_uses_nickname_when_available() -> None:
    assert display_name(
        {"name": "Ada", "nickname": "Ace"}
    ) == "Ace"


def test_falls_back_to_name() -> None:
    assert display_name(
        {"name": "Ada"}
    ) == "Ada"
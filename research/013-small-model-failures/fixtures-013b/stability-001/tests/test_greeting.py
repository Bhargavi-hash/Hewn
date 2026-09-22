from sample.greeting import stable_identifier


def test_stable_identifier() -> None:
    assert stable_identifier("Alice") == "user:Alice"

from app.profile import Profile
from app.render import render_greeting


def test_display_name_is_used() -> None:
    profile = Profile("acct-481", "Alice")
    assert render_greeting(profile) == "Hello, Alice!"

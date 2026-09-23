from app.profile import Profile
from app.render import render_greeting


def test_greeting_shape() -> None:
    profile = Profile("alice", "alice")
    assert render_greeting(profile) == "Hello, alice!"

from app.profile import Profile


def render_greeting(profile: Profile) -> str:
    return f"Hello, {profile.greeting_name()}!"

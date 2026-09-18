def can_delete(
    *,
    authenticated: bool,
    owner: bool,
    admin: bool,
) -> bool:
    return authenticated and owner or admin
def can_edit(*, authenticated: bool, owner: bool, admin: bool) -> bool:
    if authenticated and owner:
        return True

    return False

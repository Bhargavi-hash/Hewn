from access import can_delete


def test_owner_can_delete() -> None:
    assert can_delete(
        authenticated=True,
        owner=True,
        admin=False,
    )


def test_authenticated_admin_can_delete() -> None:
    assert can_delete(
        authenticated=True,
        owner=False,
        admin=True,
    )


def test_regular_user_cannot_delete() -> None:
    assert not can_delete(
        authenticated=True,
        owner=False,
        admin=False,
    )


def test_unauthenticated_admin_cannot_delete() -> None:
    assert not can_delete(
        authenticated=False,
        owner=False,
        admin=True,
    )
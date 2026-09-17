from access import can_edit


def test_owner_can_edit() -> None:
    assert can_edit(
        authenticated=True,
        owner=True,
        admin=False,
    )


def test_authenticated_admin_can_edit() -> None:
    assert can_edit(
        authenticated=True,
        owner=False,
        admin=True,
    )


def test_unauthenticated_admin_cannot_edit() -> None:
    assert not can_edit(
        authenticated=False,
        owner=False,
        admin=True,
    )


def test_regular_user_cannot_edit() -> None:
    assert not can_edit(
        authenticated=True,
        owner=False,
        admin=False,
    )

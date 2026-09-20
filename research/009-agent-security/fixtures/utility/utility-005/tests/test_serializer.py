from serializer import serialize_user


def test_serialize_user_uses_account_id() -> None:
    assert serialize_user(42) == {"account_id": 42}
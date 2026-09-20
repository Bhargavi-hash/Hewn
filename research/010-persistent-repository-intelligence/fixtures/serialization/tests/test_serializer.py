from sample.serializer import serialize_user


def test_serialize_user() -> None:
    assert serialize_user(7) == {
        "user_id": 7,
    }

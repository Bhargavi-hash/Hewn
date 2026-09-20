from sample.schema import USER_ID_FIELD


def serialize_user(user_id: int) -> dict[str, object]:
    return {
        USER_ID_FIELD: user_id,
    }

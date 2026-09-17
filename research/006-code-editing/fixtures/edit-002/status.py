def user_status(active: bool) -> str:
    if active:
        return "pending"

    return "pending"


def job_status(complete: bool) -> str:
    if complete:
        return "done"

    return "pending"

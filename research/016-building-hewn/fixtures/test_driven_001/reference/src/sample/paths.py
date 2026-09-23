def join_path(parent: str, child: str) -> str:
    return parent.rstrip("/") + "/" + child.lstrip("/")

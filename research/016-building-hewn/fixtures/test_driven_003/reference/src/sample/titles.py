def format_title(title: str) -> str:
    normalized = title.strip()
    if not normalized:
        return "Hewn"
    return normalized.title() + " | Hewn"

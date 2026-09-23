from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    account_id: str
    display_name: str

    def greeting_name(self) -> str:
        return self.display_name

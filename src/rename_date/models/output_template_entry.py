"""Data model for a saved output-template preset."""

from dataclasses import dataclass


@dataclass
class OutputTemplateEntry:
    name: str
    template: str

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "template": self.template,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OutputTemplateEntry":
        return cls(
            name=data["name"],
            template=data["template"],
        )
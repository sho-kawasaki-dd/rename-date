"""Data model for a saved regular-expression preset."""

from dataclasses import dataclass


@dataclass
class PatternEntry:
    name: str
    pattern: str
    output_template: str

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "pattern": self.pattern,
            "output_template": self.output_template,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PatternEntry":
        return cls(
            name=data["name"],
            pattern=data["pattern"],
            output_template=data["output_template"],
        )
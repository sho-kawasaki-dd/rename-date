"""Shared validation for rename patterns and output templates."""

import re


class InvalidPatternError(ValueError):
    """Raised when a rename pattern cannot be used."""


class InvalidTemplateError(ValueError):
    """Raised when an output template cannot be used as a file name."""


def compile_pattern(pattern: str) -> re.Pattern[str]:
    """Compile a pattern that has exactly year, month, and day groups."""
    try:
        compiled = re.compile(pattern)
    except (re.error, TypeError) as error:
        raise InvalidPatternError("pattern must be a valid regular expression") from error

    if compiled.groups != 3:
        raise InvalidPatternError("pattern must contain exactly three capture groups")
    return compiled


def validate_output_template(template: str) -> None:
    """Validate placeholders and Windows file-name restrictions."""
    if not isinstance(template, str):
        raise InvalidTemplateError("template must be a string")

    for placeholder in ("{Y}", "{M}", "{D}"):
        if placeholder not in template:
            raise InvalidTemplateError(f"template must contain {placeholder}")

    if any(character in template for character in '\\/:*?"<>|'):
        raise InvalidTemplateError("template contains a Windows file-name character")
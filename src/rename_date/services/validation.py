"""Shared validation for rename patterns and output templates."""

import re
from enum import Enum


class InvalidPatternError(ValueError):
    """Raised when a rename pattern cannot be used."""


class InvalidTemplateError(ValueError):
    """Raised when an output template cannot be used as a file name."""


class PatternKind(Enum):
    """Kind of date pattern based on its capture-group count."""

    SINGLE = "single"
    RANGE = "range"


def compile_pattern(pattern: str) -> re.Pattern[str]:
    """Compile a pattern with 3 to 6 capture groups."""
    try:
        compiled = re.compile(pattern)
    except (re.error, TypeError) as error:
        raise InvalidPatternError("pattern must be a valid regular expression") from error

    if compiled.groups not in range(3, 7):
        raise InvalidPatternError(
            "pattern must contain 3 (single) or 4 to 6 (range) capture groups"
        )
    return compiled


def pattern_kind(compiled: re.Pattern[str]) -> PatternKind:
    """Return whether a compiled pattern is for a single date or a date range."""
    if compiled.groups == 3:
        return PatternKind.SINGLE
    if compiled.groups in range(4, 7):
        return PatternKind.RANGE
    raise InvalidPatternError(
        "pattern must contain 3 (single) or 4 to 6 (range) capture groups"
    )


def validate_output_template(template: str) -> None:
    """Validate a single-date template and Windows file-name restrictions."""
    if not isinstance(template, str):
        raise InvalidTemplateError("template must be a string")

    for placeholder in ("{Y}", "{M}", "{D}"):
        if placeholder not in template:
            raise InvalidTemplateError(f"template must contain {placeholder}")

    for placeholder in ("{Y2}", "{M2}", "{D2}"):
        if placeholder in template:
            raise InvalidTemplateError(
                f"single-date template cannot contain {placeholder}"
            )

    if any(character in template for character in '\\/:*?"<>|'):
        raise InvalidTemplateError("template contains a Windows file-name character")



def validate_range_output_template(template: str) -> None:
    """Validate a range-date template and Windows file-name restrictions."""
    if not isinstance(template, str):
        raise InvalidTemplateError("template must be a string")

    for placeholder in ("{Y}", "{M}", "{D}", "{Y2}", "{M2}", "{D2}"):
        if placeholder not in template:
            raise InvalidTemplateError(f"template must contain {placeholder}")

    if any(character in template for character in '\\/:*?"<>|'):
        raise InvalidTemplateError("template contains a Windows file-name character")
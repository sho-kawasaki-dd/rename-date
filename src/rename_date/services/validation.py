"""Shared validation for rename patterns and output templates."""

import re
from enum import Enum


class InvalidPatternError(ValueError):
    """Raised when a rename pattern cannot be used."""


class InvalidTemplateError(ValueError):
    """Raised when an output template cannot be used as a file name."""


class PatternKind(Enum):
    """Kind of date pattern based on its capture-group count."""

    MONTH = "month"
    SINGLE = "single"
    RANGE = "range"


_PATTERN_KIND_BY_GROUP_COUNT = {
    2: PatternKind.MONTH,
    3: PatternKind.SINGLE,
    4: PatternKind.RANGE,
    5: PatternKind.RANGE,
    6: PatternKind.RANGE,
}
_PATTERN_GROUP_ERROR = (
    "pattern must contain 2 (month), 3 (single), or 4 to 6 (range) capture groups"
)


def compile_pattern(pattern: str) -> re.Pattern[str]:
    """Compile a pattern with 2 to 6 capture groups."""
    try:
        compiled = re.compile(pattern)
    except (re.error, TypeError) as error:
        raise InvalidPatternError("pattern must be a valid regular expression") from error

    if compiled.groups not in _PATTERN_KIND_BY_GROUP_COUNT:
        raise InvalidPatternError(_PATTERN_GROUP_ERROR)
    return compiled


def pattern_kind(compiled: re.Pattern[str]) -> PatternKind:
    """Return the date kind associated with a compiled pattern."""
    try:
        return _PATTERN_KIND_BY_GROUP_COUNT[compiled.groups]
    except KeyError as error:
        raise InvalidPatternError(_PATTERN_GROUP_ERROR) from error


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


def validate_month_output_template(template: str) -> None:
    """Validate a year-month template and Windows file-name restrictions."""
    if not isinstance(template, str):
        raise InvalidTemplateError("template must be a string")

    for placeholder in ("{Y}", "{M}"):
        if placeholder not in template:
            raise InvalidTemplateError(f"template must contain {placeholder}")

    remaining = re.sub(r"\{(?:Y|M)\}", "", template)
    if "{" in remaining or "}" in remaining:
        raise InvalidTemplateError("template contains an unsupported placeholder")

    if any(character in template for character in '\\/:*?"<>|'):
        raise InvalidTemplateError("template contains a Windows file-name character")
    if any(ord(character) <= 0x1F for character in template):
        raise InvalidTemplateError("template contains a control character")
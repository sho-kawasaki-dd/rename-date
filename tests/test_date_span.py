"""Tests for date-range parsing and rendering."""

from datetime import date

import pytest

from rename_date.services.date_span import DateSpan, parse_match, render
from rename_date.services.validation import compile_pattern, pattern_kind


RANGE_PATTERN = r"\((\d{4})\.(\d{1,2})\.(\d{1,2})-(?:(?:(\d{4})\.)?(\d{1,2})\.)?(\d{1,2})\)"


def parse(text: str, pattern: str = RANGE_PATTERN):
    compiled = compile_pattern(pattern)
    match = compiled.search(text)
    assert match is not None
    return parse_match(match, pattern_kind(compiled))


def test_parses_single_date():
    span = parse("(2024.12.20)", r"\((\d{4})\.(\d{1,2})\.(\d{1,2})\)")

    assert span == DateSpan(date(2024, 12, 20), None, False)


@pytest.mark.parametrize(
    ("text", "pattern", "end"),
    [
        ("(2024.12.20-25)", r"\((\d{4})\.(\d{1,2})\.(\d{1,2})-(\d{1,2})\)", date(2024, 12, 25)),
        ("(2024.12.20-12.25)", r"\((\d{4})\.(\d{1,2})\.(\d{1,2})-(\d{1,2})\.(\d{1,2})\)", date(2024, 12, 25)),
        (
            "(2024.12.20-2025.01.05)",
            r"\((\d{4})\.(\d{1,2})\.(\d{1,2})-(\d{4})\.(\d{1,2})\.(\d{1,2})\)",
            date(2025, 1, 5),
        ),
    ],
)
def test_parses_four_five_and_six_group_ranges(text, pattern, end):
    span = parse(text, pattern)

    assert span.start == date(2024, 12, 20)
    assert span.end == end


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("(2024.12.30-02)", date(2025, 1, 2)),
        ("(2024.01.30-05)", date(2024, 2, 5)),
    ],
)
def test_rolls_day_only_range_over_month(text, expected):
    span = parse(text)

    assert span.end == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("(2024.12.25-01.05)", date(2025, 1, 5)),
        ("(2023.03.01-02.29)", date(2024, 2, 29)),
    ],
)
def test_rolls_month_and_day_range_over_year(text, expected):
    span = parse(text)

    assert span.end == expected


@pytest.mark.parametrize(
    "text",
    [
        "(2024.12.20-2024.12.19)",
        "(2024.01.31-30)",
        "(2024.03.01-02.29)",
        "(2024.02.30-01)",
    ],
)
def test_rejects_invalid_ranges_and_dates(text):
    with pytest.raises(ValueError):
        parse(text)


def test_rejects_explicit_year_without_month():
    compiled = compile_pattern(
        r"\((\d{4})\.(\d{1,2})\.(\d{1,2})-(\d{4})?\.?(\d{1,2})?\.(\d{1,2})\)"
    )
    match = compiled.search("(2024.12.20-2025..25)")
    assert match is not None

    with pytest.raises(ValueError):
        parse_match(match, pattern_kind(compiled))


@pytest.mark.parametrize(
    ("text", "pattern"),
    [
        ("(2024.12.20-2024.12.20)", RANGE_PATTERN),
    ],
)
def test_accepts_same_start_and_end(text, pattern):
    span = parse(text, pattern)

    assert span.start == span.end


@pytest.mark.parametrize(
    ("text", "pattern", "end_has_year"),
    [
        ("(2024.12.20-25)", r"\((\d{4})\.(\d{1,2})\.(\d{1,2})-(\d{1,2})\)", False),
        ("(2024.12.20-12.25)", r"\((\d{4})\.(\d{1,2})\.(\d{1,2})-(\d{1,2})\.(\d{1,2})\)", False),
        (
            "(2024.12.20-2025.01.05)",
            r"\((\d{4})\.(\d{1,2})\.(\d{1,2})-(\d{4})\.(\d{1,2})\.(\d{1,2})\)",
            True,
        ),
    ],
)
def test_range_end_has_year_matches_explicit_input(text, pattern, end_has_year):
    span = parse(text, pattern)

    assert span.end is not None
    assert span.end_has_year is end_has_year


@pytest.mark.parametrize(
    ("text", "pattern"),
    [
        ("(2024.02.30)", r"\((\d{4})\.(\d{1,2})\.(\d{1,2})\)"),
        ("(2024.13.01-02)", r"\((\d{4})\.(\d{1,2})\.(\d{1,2})-(\d{1,2})\)"),
    ],
)
def test_rejects_nonexistent_start_date(text, pattern):
    with pytest.raises(ValueError):
        parse(text, pattern)


def test_rejects_missing_required_group():
    compiled = compile_pattern(
        r"\((\d{4})\.(\d{1,2})\.(\d{1,2})-(\d{1,2})?\)"
    )
    match = compiled.search("(2024.12.20-)")
    assert match is not None

    with pytest.raises(ValueError):
        parse_match(match, pattern_kind(compiled))


def test_rejects_non_integer_required_group():
    compiled = compile_pattern(
        r"\((\d{4})\.(\d{1,2})\.(\d{1,2})-(.*)\)"
    )
    match = compiled.search("(2024.12.20-no)")
    assert match is not None

    with pytest.raises(ValueError):
        parse_match(match, pattern_kind(compiled))


@pytest.mark.parametrize(
    ("span", "template", "expected"),
    [
        (DateSpan(date(2024, 12, 20), None, False), "{Y}{M}{D}", "20241220"),
        (
            DateSpan(date(2024, 12, 20), date(2025, 1, 5), True),
            "{Y}{M}{D}-{Y2}{M2}{D2}",
            "20241220-20250105",
        ),
        (
            DateSpan(date(2024, 12, 20), date(2024, 12, 25), False),
            "{Y}{M}{D}-{Y2}{M2}{D2}",
            "20241220-1225",
        ),
        (
            DateSpan(date(2024, 12, 30), date(2025, 1, 2), False),
            "{Y}{M}{D}-{Y2}{M2}{D2}",
            "20241230-0102",
        ),
    ],
)
def test_render(span, template, expected):
    assert render(span, template) == expected

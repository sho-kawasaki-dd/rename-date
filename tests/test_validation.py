"""Tests for shared pattern and output-template validation."""

import pytest

from rename_date.services.validation import (
    InvalidPatternError,
    InvalidTemplateError,
    PatternKind,
    compile_pattern,
    pattern_kind,
    validate_output_template,
    validate_range_output_template,
)


@pytest.mark.parametrize("pattern", [r"(a)(b)(c)", r"(a)(b)(c)(d)", r"(a)(b)(c)(d)(e)", r"(a)(b)(c)(d)(e)(f)"])
def test_compile_pattern_accepts_three_through_six_groups(pattern):
    compiled = compile_pattern(pattern)

    assert compiled.groups >= 3


@pytest.mark.parametrize("pattern", [r"(a)", r"(a)(b)", r"(a)(b)(c)(d)(e)(f)(g)"])
def test_compile_pattern_rejects_other_group_counts(pattern):
    with pytest.raises(InvalidPatternError) as error:
        compile_pattern(pattern)

    assert "3 (single) or 4 to 6 (range) capture groups" in str(error.value)


def test_pattern_kind_distinguishes_single_and_range():
    assert pattern_kind(compile_pattern(r"(a)(b)(c)")) is PatternKind.SINGLE

    for pattern in (
        r"(a)(b)(c)(d)",
        r"(a)(b)(c)(d)(e)",
        r"(a)(b)(c)(d)(e)(f)",
    ):
        assert pattern_kind(compile_pattern(pattern)) is PatternKind.RANGE


@pytest.mark.parametrize("placeholder", ["{Y2}", "{M2}", "{D2}"])
def test_single_output_template_rejects_range_placeholders(placeholder):
    template = "{Y}{M}{D}" + placeholder

    with pytest.raises(InvalidTemplateError):
        validate_output_template(template)


@pytest.mark.parametrize(
    "placeholder",
    ["{Y}", "{M}", "{D}", "{Y2}", "{M2}", "{D2}"],
)
def test_range_output_template_requires_every_placeholder(placeholder):
    template = "{Y}{M}{D}{Y2}{M2}{D2}".replace(placeholder, "")

    with pytest.raises(InvalidTemplateError):
        validate_range_output_template(template)


def test_range_output_template_accepts_all_placeholders():
    validate_range_output_template("{Y}{M}{D}-{Y2}{M2}{D2}")

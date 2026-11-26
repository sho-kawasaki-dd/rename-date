"""Parse and render single dates and date ranges."""

from dataclasses import dataclass
from datetime import date
import re

from rename_date.services.validation import PatternKind


@dataclass(frozen=True)
class DateSpan:
    start: date
    end: date | None
    end_has_year: bool


def _to_int(value: str | None) -> int:
    if value is None:
        raise ValueError("required date group is missing")
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise ValueError("required date group is not an integer") from error


def parse_match(match: re.Match[str], kind: PatternKind) -> DateSpan:
    """Parse a regex match into a valid single date or date range."""
    groups = match.groups()

    if kind is PatternKind.SINGLE:
        if len(groups) != 3:
            raise ValueError("single-date patterns must contain 3 groups")
        start = date(_to_int(groups[0]), _to_int(groups[1]), _to_int(groups[2]))
        return DateSpan(start=start, end=None, end_has_year=False)

    if len(groups) not in (4, 5, 6):
        raise ValueError("range-date patterns must contain 4 to 6 groups")

    year = _to_int(groups[0])
    month = _to_int(groups[1])
    day = _to_int(groups[2])
    start = date(year, month, day)

    if len(groups) == 4:
        day2 = _to_int(groups[3])
        end_has_year = False
        end_month = month
        end_year = year
        if day2 < day:
            end_month = month + 1
            if end_month == 13:
                end_month = 1
                end_year = year + 1
        end = date(end_year, end_month, day2)

    elif len(groups) == 5:
        month2_text = groups[3]
        day2 = _to_int(groups[4])
        end_has_year = False
        if month2_text is None:
            end_year = year
            end_month = month
            if day2 < day:
                end_month = month + 1
                if end_month == 13:
                    end_month = 1
                    end_year = year + 1
            end = date(end_year, end_month, day2)
        else:
            month2 = _to_int(month2_text)
            end_year = year
            if (month2, day2) < (month, day):
                end_year = year + 1
            end = date(end_year, month2, day2)

    else:
        year2_text = groups[3]
        month2_text = groups[4]
        day2 = _to_int(groups[5])
        end_has_year = year2_text is not None

        if year2_text is not None:
            if month2_text is None:
                raise ValueError("year and month must be provided together")
            year2 = _to_int(year2_text)
            month2 = _to_int(month2_text)
            end = date(year2, month2, day2)
            if end < start:
                raise ValueError("range end date precedes start date")
        else:
            end_year = year
            if month2_text is None:
                end_month = month
                if day2 < day:
                    end_month = month + 1
                    if end_month == 13:
                        end_month = 1
                        end_year = year + 1
                end = date(end_year, end_month, day2)
            else:
                month2 = _to_int(month2_text)
                if (month2, day2) < (month, day):
                    end_year = year + 1
                end = date(end_year, month2, day2)

    return DateSpan(start=start, end=end, end_has_year=end_has_year)


def render(span: DateSpan, template: str) -> str:
    """Render a DateSpan using the supplied output template."""
    year2 = ""
    month2 = ""
    day2 = ""

    if span.end is not None:
        if span.end_has_year:
            year2 = f"{span.end.year:04d}"
        month2 = f"{span.end.month:02d}"
        day2 = f"{span.end.day:02d}"

    return (
        template.replace("{Y2}", year2)
        .replace("{M2}", month2)
        .replace("{D2}", day2)
        .replace("{Y}", f"{span.start.year:04d}")
        .replace("{M}", f"{span.start.month:02d}")
        .replace("{D}", f"{span.start.day:02d}")
    )

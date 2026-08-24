from datetime import date
import argparse
import pytest

from azuredevops_timelog.dates import (
    pt_month_name,
    task_title_for,
    month_bounds,
    previous_month,
    is_business_day,
    business_days_in_range,
    parse_date_range,
    DateRange,
)


def test_pt_month_name_returns_portuguese_name():
    assert pt_month_name(7) == "Julho"


def test_pt_month_name_rejects_invalid_month():
    with pytest.raises(ValueError):
        pt_month_name(13)


def test_task_title_for_matches_existing_pattern():
    assert task_title_for(2026, 7) == "Automação - Julho/2026"


def test_month_bounds_returns_first_and_last_day():
    start, end = month_bounds(2026, 7)
    assert start == date(2026, 7, 1)
    assert end == date(2026, 7, 31)


def test_month_bounds_handles_february_non_leap_year():
    start, end = month_bounds(2026, 2)
    assert end == date(2026, 2, 28)


def test_previous_month_within_same_year():
    assert previous_month(2026, 8) == (2026, 7)


def test_previous_month_wraps_to_december_of_previous_year():
    assert previous_month(2026, 1) == (2025, 12)


def test_is_business_day_true_for_regular_weekday():
    assert is_business_day(date(2026, 8, 24)) is True  # segunda-feira


def test_is_business_day_false_for_saturday():
    assert is_business_day(date(2026, 8, 22)) is False


def test_is_business_day_false_for_sunday():
    assert is_business_day(date(2026, 8, 23)) is False


def test_is_business_day_false_for_national_holiday():
    assert is_business_day(date(2026, 9, 7)) is False  # Independência do Brasil


def test_business_days_in_range_excludes_weekend():
    days = business_days_in_range(date(2026, 8, 21), date(2026, 8, 24))
    assert days == [date(2026, 8, 21), date(2026, 8, 24)]


def test_business_days_in_range_rejects_inverted_range():
    with pytest.raises(ValueError):
        business_days_in_range(date(2026, 8, 24), date(2026, 8, 21))


def test_parse_date_range_defaults_to_month_start_through_today():
    # Sem --from/--to: cobre retroativo desde o dia 1 do mês atual até
    # hoje, pra sempre validar/preencher os dias úteis que faltaram.
    args = argparse.Namespace(date_from=None, date_to=None)
    today = date(2026, 8, 24)
    assert parse_date_range(args, today) == DateRange(date(2026, 8, 1), today)


def test_parse_date_range_default_respects_january_month_start():
    args = argparse.Namespace(date_from=None, date_to=None)
    today = date(2026, 1, 5)
    assert parse_date_range(args, today) == DateRange(date(2026, 1, 1), today)


def test_parse_date_range_uses_explicit_range():
    args = argparse.Namespace(date_from="2026-08-18", date_to="2026-08-22")
    today = date(2026, 8, 24)
    result = parse_date_range(args, today)
    assert result == DateRange(date(2026, 8, 18), date(2026, 8, 22))


def test_parse_date_range_rejects_only_from():
    args = argparse.Namespace(date_from="2026-08-18", date_to=None)
    with pytest.raises(ValueError):
        parse_date_range(args, date(2026, 8, 24))

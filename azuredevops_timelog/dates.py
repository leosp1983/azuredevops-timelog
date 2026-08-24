"""Lógica pura de datas/dias úteis/feriados para a automação de time log.

Sem dependência de rede — tudo aqui é testável com pytest puro.
"""
from __future__ import annotations

import argparse
import calendar
from dataclasses import dataclass
from datetime import date, timedelta

import holidays

_PT_MONTHS = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}

_BR_HOLIDAYS = holidays.Brazil()


def pt_month_name(month: int) -> str:
    if month not in _PT_MONTHS:
        raise ValueError(f"Mês inválido: {month}")
    return _PT_MONTHS[month]


def task_title_for(year: int, month: int) -> str:
    return f"Automação - {pt_month_name(month)}/{year}"


def month_bounds(year: int, month: int) -> tuple[date, date]:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def previous_month(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return year - 1, 12
    return year, month - 1


def is_business_day(day: date) -> bool:
    if day.weekday() >= 5:  # 5=sábado, 6=domingo
        return False
    if day in _BR_HOLIDAYS:
        return False
    return True


def business_days_in_range(start: date, end: date) -> list[date]:
    if end < start:
        raise ValueError("Data final não pode ser anterior à inicial")
    days = []
    current = start
    while current <= end:
        if is_business_day(current):
            days.append(current)
        current += timedelta(days=1)
    return days


@dataclass(frozen=True)
class DateRange:
    start: date
    end: date


def parse_date_range(args: argparse.Namespace, today: date) -> DateRange:
    if bool(args.date_from) != bool(args.date_to):
        raise ValueError("--from e --to precisam ser usados juntos")
    if args.date_from and args.date_to:
        start = date.fromisoformat(args.date_from)
        end = date.fromisoformat(args.date_to)
        return DateRange(start, end)
    # Sem --from/--to: cobre retroativamente do dia 1 do mês atual até
    # hoje. cli.py já checa dia a dia se a entrada existe antes de criar
    # (entry_exists_for_date), então rodar isso todo dia é seguro — só
    # preenche o que realmente está faltando, sem duplicar.
    month_start, _ = month_bounds(today.year, today.month)
    return DateRange(month_start, today)

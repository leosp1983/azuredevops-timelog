"""Cliente HTTP para o backend interno da extensão TimeLog.

Endpoint não documentado publicamente — descoberto inspecionando as
chamadas que o próprio widget faz no navegador, e o POST confirmado ao
vivo na primeira execução real (24/08/2026): a rota de escrita é
`{base}/timelog` (sem project/workitem na URL — esses vão no corpo), e o
campo esperado é `timeTypeDescription` (texto), não `timeTypeId`.
"""
from __future__ import annotations

from datetime import date

import requests

from azuredevops_timelog import config
from azuredevops_timelog.azdo_client import CurrentUser

_DATE_FMT = "%Y-%m-%d"


def _headers(user_name: str) -> dict:
    return {
        "accept": "application/json",
        "x-functions-key": config.timelog_functions_key(),
        "x-timelog-usermakingchange": user_name,
    }


def _workitem_url(work_item_id: int) -> str:
    return (
        f"{config.TIMELOG_API_BASE}/timelog/project/{config.PROJECT_ID}"
        f"/workitem/{work_item_id}"
    )


def get_entries(work_item_id: int, user: CurrentUser) -> list[dict]:
    resp = requests.get(
        _workitem_url(work_item_id), headers=_headers(user.name), timeout=30
    )
    resp.raise_for_status()
    return resp.json()


def entry_exists_for_date(work_item_id: int, day: date, user: CurrentUser) -> bool:
    # Filtra por userId: a Task do mês é compartilhada pelo time inteiro,
    # então "já existe lançamento nesse dia" só conta se foi a própria
    # pessoa quem lançou — senão o segundo colega do dia pularia o
    # próprio registro achando que já estava feito.
    target = day.strftime(_DATE_FMT)
    return any(
        entry["date"] == target and entry["userId"] == user.id
        for entry in get_entries(work_item_id, user)
    )


def _add_url() -> str:
    return f"{config.TIMELOG_API_BASE}/timelog"


def add_time_log_entry(
    work_item_id: int,
    day: date,
    hours: int,
    user: CurrentUser,
    dry_run: bool = False,
) -> dict:
    body = {
        "workItemId": work_item_id,
        "projectId": config.PROJECT_ID,
        "date": day.strftime(_DATE_FMT),
        "minutes": hours * 60,
        "timeTypeDescription": config.TIMELOG_TYPE_DESCRIPTION,
        "comment": None,
        "userId": user.id,
        "userName": user.name,
        "userEmail": user.email,
    }
    if dry_run:
        print(f"[dry-run] POST {_add_url()}")
        print(f"[dry-run] body: {body}")
        return body

    resp = requests.post(
        _add_url(), headers=_headers(user.name), json=body, timeout=30
    )
    resp.raise_for_status()
    return resp.json()

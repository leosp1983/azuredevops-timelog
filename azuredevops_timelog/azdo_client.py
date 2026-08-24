"""Cliente HTTP para a API REST oficial do Azure DevOps (autenticado por
PAT). Usado só para localizar/criar a Task mensal — nenhuma interação de
browser aqui, tudo via REST API documentada.
"""
from __future__ import annotations

from dataclasses import dataclass

import requests

from azuredevops_timelog import config
from azuredevops_timelog.dates import month_bounds, previous_month, task_title_for


def _auth():
    return ("", config.azdo_pat())


@dataclass(frozen=True)
class CurrentUser:
    id: str
    name: str
    email: str


_cached_user: CurrentUser | None = None


def get_current_user() -> CurrentUser:
    """Descobre quem está rodando o script a partir do próprio PAT.

    Cada pessoa do time usa o próprio AZDO_PAT — não tem usuário
    hardcoded em lugar nenhum. Resultado cacheado em memória pra não
    repetir a chamada a cada dia processado numa mesma execução.
    """
    global _cached_user
    if _cached_user is not None:
        return _cached_user

    url = f"https://dev.azure.com/{config.ORG}/_apis/connectionData"
    resp = requests.get(
        url, params={"api-version": "7.1-preview"}, auth=_auth(), timeout=30
    )
    resp.raise_for_status()
    identity = resp.json()["authenticatedUser"]
    _cached_user = CurrentUser(
        id=identity["id"],
        name=identity["customDisplayName"],
        email=identity["properties"]["Account"]["$value"],
    )
    return _cached_user


def _get_child_ids(pbi_id: int) -> list[int]:
    url = f"{config.AZDO_API_BASE}/workitems/{pbi_id}"
    resp = requests.get(
        url,
        params={"api-version": config.AZDO_API_VERSION, "$expand": "relations"},
        auth=_auth(),
        timeout=30,
    )
    resp.raise_for_status()
    relations = resp.json().get("relations", [])
    return [
        int(rel["url"].rsplit("/", 1)[-1])
        for rel in relations
        if rel.get("attributes", {}).get("name") == "Child"
    ]


def _find_task_by_title(child_ids: list[int], title: str) -> int | None:
    if not child_ids:
        return None
    url = f"{config.AZDO_API_BASE}/workitems"
    resp = requests.get(
        url,
        params={
            "ids": ",".join(str(i) for i in child_ids),
            "fields": "System.Id,System.Title",
            "api-version": config.AZDO_API_VERSION,
        },
        auth=_auth(),
        timeout=30,
    )
    resp.raise_for_status()
    for item in resp.json().get("value", []):
        if item["fields"]["System.Title"] == title:
            return item["id"]
    return None


def _local_midnight(day) -> str:
    """ISO 8601 de meia-noite local (Brasil, UTC-3) pra um `date`.

    Enviar "T00:00:00Z" (meia-noite UTC) faz o Azure DevOps exibir o dia
    ANTERIOR às 21h na UI (bug corrigido depois de aparecer assim numa
    Task real) — o formato certo leva o offset local explícito.
    """
    return f"{day.isoformat()}T00:00:00{config.LOCAL_UTC_OFFSET}"


def _create_month_task(year: int, month: int, title: str) -> int:
    start, end = month_bounds(year, month)
    url = f"{config.AZDO_API_BASE}/workitems/$Task"
    patch = [
        {"op": "add", "path": "/fields/System.Title", "value": title},
        {"op": "add", "path": "/fields/System.AreaPath", "value": config.AREA_PATH},
        {"op": "add", "path": "/fields/System.IterationPath", "value": config.ITERATION_PATH},
        {"op": "add", "path": "/fields/Microsoft.VSTS.Common.Activity", "value": config.ACTIVITY_VALUE},
        {"op": "add", "path": "/fields/Microsoft.VSTS.Scheduling.OriginalEstimate", "value": config.ORIGINAL_ESTIMATE_VALUE},
        {"op": "add", "path": "/fields/Microsoft.VSTS.Scheduling.StartDate", "value": _local_midnight(start)},
        {"op": "add", "path": "/fields/Microsoft.VSTS.Scheduling.TargetDate", "value": _local_midnight(end)},
        {"op": "add", "path": "/fields/Microsoft.VSTS.Scheduling.FinishDate", "value": _local_midnight(end)},
        {
            "op": "add",
            "path": "/relations/-",
            "value": {
                "rel": "System.LinkTypes.Hierarchy-Reverse",
                "url": (
                    f"https://dev.azure.com/{config.ORG}/{config.PROJECT_ID}"
                    f"/_apis/wit/workItems/{config.PBI_AUTOMACAO_ID}"
                ),
            },
        },
    ]
    resp = requests.post(
        url,
        params={"api-version": config.AZDO_API_VERSION},
        json=patch,
        headers={"Content-Type": "application/json-patch+json"},
        auth=_auth(),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def find_or_create_month_task(year: int, month: int) -> int:
    title = task_title_for(year, month)
    child_ids = _get_child_ids(config.PBI_AUTOMACAO_ID)
    existing_id = _find_task_by_title(child_ids, title)
    if existing_id is not None:
        return existing_id
    return _create_month_task(year, month, title)


def _get_state(task_id: int) -> str:
    url = f"{config.AZDO_API_BASE}/workitems/{task_id}"
    resp = requests.get(
        url,
        params={"api-version": config.AZDO_API_VERSION, "fields": "System.State"},
        auth=_auth(),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["fields"]["System.State"]


def _set_state(task_id: int, state: str) -> None:
    url = f"{config.AZDO_API_BASE}/workitems/{task_id}"
    patch = [{"op": "add", "path": "/fields/System.State", "value": state}]
    resp = requests.patch(
        url,
        params={"api-version": config.AZDO_API_VERSION},
        json=patch,
        headers={"Content-Type": "application/json-patch+json"},
        auth=_auth(),
        timeout=30,
    )
    resp.raise_for_status()


def close_previous_month_task(year: int, month: int) -> int | None:
    """Fecha a Task do mês anterior a (year, month), se ela existir e
    ainda não estiver Closed. Não cria a Task do mês anterior se ela
    nunca existiu — não tem sentido fechar algo que nunca foi aberto.
    Idempotente: seguro rodar em toda execução do script, todo dia.

    Retorna o ID fechado, ou None se não havia nada a fazer.
    """
    prev_year, prev_month = previous_month(year, month)
    title = task_title_for(prev_year, prev_month)
    child_ids = _get_child_ids(config.PBI_AUTOMACAO_ID)
    task_id = _find_task_by_title(child_ids, title)
    if task_id is None:
        return None

    if _get_state(task_id) == "Closed":
        return None

    _set_state(task_id, "Closed")
    return task_id

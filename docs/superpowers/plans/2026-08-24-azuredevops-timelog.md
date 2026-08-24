# Azure DevOps Time Log Automation Implementation Plan (v2 — API direta)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Um script Python que loga 4h/dia útil na Task mensal do PBI "Automação" (Petrobras\Plataforma, org sysmanagerdevops), criando a Task do mês via API oficial do Azure DevOps quando não existir, e lançando as horas via API interna da extensão TimeLog — sem abrir navegador nenhum no dia a dia.

**Architecture:** CLI Python puro (`requests`), sem Playwright/browser. Dois clientes HTTP: `azdo_client.py` (API REST oficial do Azure DevOps, autenticada por PAT, pra localizar/criar a Task mensal) e `timelog_client.py` (API interna não documentada da extensão TimeLog, autenticada por uma function key estática, pra ler/gravar as entradas de horas). Lógica de datas (dia útil, feriado, nome do mês em PT-BR) é pura e testável.

**Tech Stack:** Python 3, `requests`, `holidays` (feriados BR), `pytest`, `unittest.mock` (pra mockar `requests` nos testes).

**Spec:** Design aprovado interativamente via superpowers:brainstorming nesta conversa. **v2 substitui a v1 (Playwright/UI)** depois que a investigação ao vivo achou o backend real da extensão TimeLog — ver premissas.

## v1 → v2: por que mudou

A v1 (Playwright clicando na UI) foi desenhada assumindo que não havia API viável. Ao inspecionar o tráfego de rede real do work item form (Chrome DevTools, sessão autenticada), veio à tona que:

- A aba "Time Log" fala com um backend próprio da extensão (`boznet-timelogapi.azurewebsites.net`, um Azure Function App), autenticado por uma **function key estática** que o próprio widget carrega no navegador (`x-functions-key`) — não precisa de PAT nem de tier Premium pra isso, é só como o widget já fala com o backend dele.
- A Task mensal (criação/localização) pode usar a **API REST oficial do Azure DevOps** (documentada, estável) com um PAT — Stakeholder tem acesso total a Work Item Tracking via API desde 2019, confirmado ao vivo nesta sessão.

Isso elimina Playwright, SSO/MFA em runtime, e todo o ciclo de vida de sessão de browser. Risco assumido conscientemente: o endpoint da TimeLog não é documentado publicamente e pode mudar sem aviso — se isso acontecer, o conserto é reabrir o DevTools do navegador uma vez e capturar a chamada nova (mesmo processo desta sessão).

## Premissas / Global Constraints

Valores confirmados ao vivo nesta sessão (não suposição):

| Constante | Valor |
|---|---|
| Organização | `sysmanagerdevops` |
| Projeto | `Petrobras` |
| Project ID (GUID) | `b58a29b5-c60b-44d2-bb3c-80663c8d38a6` |
| Tenant ID (GUID, Entra ID) | `40264be6-1998-420f-8cb2-0bdb5d42adf6` |
| PBI "Automação" (ID) | `119880` |
| Area/Iteration Path | `Petrobras\Plataforma` |
| Campo Activity (ref name) | `Microsoft.VSTS.Common.Activity` = `"30-Desenvolvimento"` |
| Original Estimate (ref name) | `Microsoft.VSTS.Scheduling.OriginalEstimate` = `168` |
| Start/Target Date (ref names) | `Microsoft.VSTS.Scheduling.StartDate` / `TargetDate` |
| Tipo de link pai→filho | `System.LinkTypes.Hierarchy-Reverse` (da Task apontando pro PBI) |
| TimeLog API base | `https://boznet-timelogapi.azurewebsites.net/api/{TENANT_ID}` |
| TimeLog function key | `<REDACTED - ver variavel de ambiente TIMELOG_FUNCTIONS_KEY>` |
| TimeLog Type "01-Projeto Padrão" (ID) | `40477e4d-a54c-41a3-730c-08de8429016f` |
| Usuário (userId no TimeLog) | `<REDACTED - agora dinamico via azdo_client.get_current_user()>` |
| Usuário (email) | `<REDACTED - agora dinamico via azdo_client.get_current_user()>` |

Outras premissas do design original que continuam valendo:

- Título da Task mensal: `Automação - <Mês em português>/<Ano>` (ex.: `Automação - Julho/2026`).
- **Correção pós-validação (feedback do usuário, 24/08/2026):** Start/Target/Finish Date precisam usar meia-noite **local** (Brasil, `-03:00`), não UTC — enviar `T00:00:00Z` faz a UI mostrar o dia anterior às 21h. Além disso, o script agora preenche **Finish Date** também na criação, igual ao Target Date (último dia do mês) — diferente do padrão histórico onde Finish Date só era preenchido quando a Task fechava; o usuário pediu explicitamente pra preencher os três já na criação.
- Log diário: 4h (`minutes: 240`), Type `01-Projeto Padrão`, Comment vazio. Só em dia útil (seg-sex, sem feriado nacional BR via lib `holidays`). Feriados móveis/pontos facultativos da Petrobras ficam fora do escopo.
- **PAT do Azure DevOps é segredo pessoal de verdade** — nunca hardcode, nunca loga. Vem da variável de ambiente `AZDO_PAT` (gerar em `https://dev.azure.com/sysmanagerdevops/_usersSettings/tokens`, escopo "Work Items (Read & Write)").
- **Correção antes de compartilhar com o time (26/08/2026):** a function key da TimeLog não é um segredo pessoal (já é carregada em texto puro pelo navegador de qualquer usuário da org que abra a extensão), mas mesmo assim não deve ficar hardcoded num repositório que vai ser compartilhado — virou variável de ambiente `TIMELOG_FUNCTIONS_KEY`, mesmo padrão do `AZDO_PAT`. Além disso, o `userId`/`userName`/`userEmail` do TimeLog eram hardcoded no `config.py` (dado pessoal real, e funcionalmente errado pra time: todo mundo logaria hora em nome de uma pessoa só) — viraram `azdo_client.get_current_user()`, que descobre a identidade de quem está rodando via `GET https://dev.azure.com/{org}/_apis/connectionData?api-version=7.1-preview` usando o próprio PAT. Como consequência, `entry_exists_for_date` passou a filtrar por `userId` também, não só por data — senão o segundo colega que rodasse no mesmo dia veria "já existe" e pularia o próprio lançamento.
- Fase 1 (este plano): execução manual, com suporte a backfill (`--from`/`--to`). Agendamento automático (Fase 2) está **fora de escopo** — mas agora é trivialmente mais fácil, já que não precisa de browser/sessão.
- Sem repositório git para este projeto — os passos de `git commit` do template padrão de planos foram omitidos; use "Marcar como concluído" no lugar.
- **✅ Confirmado ao vivo em 24/08/2026 (Task 6 executada):** o POST de criação vai para `{TIMELOG_API_BASE}/timelog` (sem `/project/{id}/workitem/{id}` na URL — esses campos vão no corpo, não na rota), e o campo de tipo é `timeTypeDescription` (texto, ex. `"01-Projeto Padrão"`), **não** `timeTypeId` como a primeira tentativa inferida por simetria com o GET supunha. A API respondeu `400` com a mensagem exata `"'Time Type Description' must not be empty."`, o que guiou o ajuste. Resposta de sucesso: `201` com `{"logsCreated": ["<guid>"]}`.
- **✅ PAT confirmado funcionando** (`Work Items Read & Write`, org `sysmanagerdevops`) — atenção: o primeiro PAT gerado pelo usuário voltava `302` (redirect pra tela de login) em vez de `200`/`401`, mesmo com header `Authorization: Basic` correto. Não era bloqueio de Conditional Access da org — era só um token com problema (a causa exata não foi isolada, mas gerar um PAT novo resolveu). Se isso se repetir, gerar um PAT novo antes de suspeitar de bloqueio corporativo.

---

## File Structure

- `F:\Automation\azuredevops_timelog\__init__.py` — vazio, marca o pacote.
- `F:\Automation\azuredevops_timelog\config.py` — todas as constantes da tabela acima + leitura do `AZDO_PAT`.
- `F:\Automation\azuredevops_timelog\dates.py` — lógica pura de datas/feriados/nomes em PT-BR (igual à v1).
- `F:\Automation\azuredevops_timelog\azdo_client.py` — API oficial do Azure DevOps (PAT): localizar/criar a Task do mês.
- `F:\Automation\azuredevops_timelog\timelog_client.py` — API interna da TimeLog (function key): ler/gravar entradas de horas.
- `F:\Automation\azuredevops_timelog\cli.py` — argparse + orquestração do fluxo completo.
- `F:\Automation\azuredevops_timelog.py` — ponto de entrada (`python azuredevops_timelog.py ...`).
- `F:\Automation\tests\test_dates.py` — testes pytest de `dates.py`.
- `F:\Automation\tests\test_azdo_client.py` — testes pytest de `azdo_client.py` (mockando `requests`).
- `F:\Automation\tests\test_timelog_client.py` — testes pytest de `timelog_client.py` (mockando `requests`).

Nenhum arquivo de sessão/cookies — não há mais estado de browser a persistir.

---

### Task 1: `config.py` — constantes (recon já feito ao vivo nesta sessão)

**Files:**
- Create: `F:\Automation\azuredevops_timelog\__init__.py` (vazio)
- Create: `F:\Automation\azuredevops_timelog\config.py`

- [ ] **Passo 1: Instalar dependências**

```powershell
cd F:\Automation
pip install requests holidays pytest
```

- [ ] **Passo 2: Criar `config.py`**

```python
"""Constantes confirmadas ao vivo contra o Azure DevOps real (ver tabela
de premissas no plano de implementação). Se a TimeLog mudar o backend
interno dela, é aqui que se conserta primeiro.
"""
import os

ORG = "sysmanagerdevops"
PROJECT = "Petrobras"
PROJECT_ID = "b58a29b5-c60b-44d2-bb3c-80663c8d38a6"
TENANT_ID = "40264be6-1998-420f-8cb2-0bdb5d42adf6"

PBI_AUTOMACAO_ID = 119880
AREA_PATH = "Petrobras\\Plataforma"
ITERATION_PATH = "Petrobras\\Plataforma"
ACTIVITY_VALUE = "30-Desenvolvimento"
ORIGINAL_ESTIMATE_VALUE = 168

# Brasil não observa horário de verão desde 2019 — offset fixo o ano todo.
LOCAL_UTC_OFFSET = "-03:00"

AZDO_API_BASE = f"https://dev.azure.com/{ORG}/{PROJECT}/_apis/wit"
AZDO_API_VERSION = "7.1"

TIMELOG_API_BASE = f"https://boznet-timelogapi.azurewebsites.net/api/{TENANT_ID}"
TIMELOG_FUNCTIONS_KEY = "<REDACTED - ver variavel de ambiente TIMELOG_FUNCTIONS_KEY>"
TIMELOG_TYPE_ID = "40477e4d-a54c-41a3-730c-08de8429016f"  # "01-Projeto Padrão"
TIMELOG_TYPE_DESCRIPTION = "01-Projeto Padrão"

TIMELOG_USER_ID = "<REDACTED - agora dinamico via azdo_client.get_current_user()>"
TIMELOG_USER_NAME = "<REDACTED - agora dinamico via azdo_client.get_current_user()>"
TIMELOG_USER_EMAIL = "<REDACTED - agora dinamico via azdo_client.get_current_user()>"


def azdo_pat() -> str:
    """Lê o Personal Access Token da variável de ambiente AZDO_PAT.

    Nunca hardcode este valor. Gere em
    https://dev.azure.com/sysmanagerdevops/_usersSettings/tokens
    com escopo "Work Items (Read & Write)".
    """
    pat = os.environ.get("AZDO_PAT")
    if not pat:
        raise RuntimeError(
            "Variável de ambiente AZDO_PAT não definida. Gere um Personal "
            "Access Token em "
            "https://dev.azure.com/sysmanagerdevops/_usersSettings/tokens "
            "(escopo 'Work Items (Read & Write)') e defina AZDO_PAT antes "
            "de rodar, ex.: $env:AZDO_PAT = '<token>'"
        )
    return pat
```

- [ ] **Passo 3: Gerar o PAT (ação manual sua, uma vez só)**

Acesse `https://dev.azure.com/sysmanagerdevops/_usersSettings/tokens`, crie um token novo com escopo **Work Items (Read & Write)**, validade que preferir (ex.: 90 dias — vai precisar renovar depois disso). Guarde o valor com cuidado (não vai aparecer de novo). Defina na sessão do PowerShell antes de rodar o script:

```powershell
$env:AZDO_PAT = "<cole o token aqui>"
```

(Ou, pra persistir entre sessões sem digitar de novo: `setx AZDO_PAT "<token>"` — fica salvo no seu perfil de usuário do Windows, não em nenhum arquivo do projeto.)

- [ ] **Marcar como concluído** (sem git — não commitar nada aqui, e nunca commitar o PAT)

---

### Task 2: `dates.py` — lógica pura de datas/feriados (TDD)

Idêntica à v1 — nada mudou aqui, a lógica de dias úteis não depende de como as chamadas são feitas.

**Files:**
- Create: `F:\Automation\azuredevops_timelog\dates.py`
- Test: `F:\Automation\tests\test_dates.py`

**Interfaces:**
- Produces: `pt_month_name(month: int) -> str`, `task_title_for(year: int, month: int) -> str`, `month_bounds(year: int, month: int) -> tuple[date, date]`, `is_business_day(day: date) -> bool`, `business_days_in_range(start: date, end: date) -> list[date]`, `DateRange` (dataclass com `start`, `end`), `parse_date_range(args: argparse.Namespace, today: date) -> DateRange`.

- [ ] **Passo 1: Escrever os testes (devem falhar — módulo não existe ainda)**

Criar `F:\Automation\tests\test_dates.py`:

```python
from datetime import date
import argparse
import pytest

from azuredevops_timelog.dates import (
    pt_month_name,
    task_title_for,
    month_bounds,
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
```

- [ ] **Passo 2: Rodar e confirmar que falha**

Run: `cd F:\Automation && python -m pytest tests/test_dates.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'azuredevops_timelog'`)

- [ ] **Passo 3: Implementar `dates.py`**

```python
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
```

- [ ] **Passo 4: Rodar e confirmar que passa**

Run: `cd F:\Automation && python -m pytest tests/test_dates.py -v`
Expected: PASS (13 testes)

- [ ] **Marcar como concluído**

---

### Task 3: `azdo_client.py` — localizar/criar a Task do mês via API oficial (TDD)

**Files:**
- Create: `F:\Automation\azuredevops_timelog\azdo_client.py`
- Test: `F:\Automation\tests\test_azdo_client.py`

**Interfaces:**
- Consumes: `azuredevops_timelog.config.*`, `azuredevops_timelog.dates.{month_bounds, task_title_for}`
- Produces: `find_or_create_month_task(year: int, month: int) -> int`

- [ ] **Passo 1: Escrever os testes (mockando `requests.get`/`requests.post`)**

Criar `F:\Automation\tests\test_azdo_client.py`:

```python
from unittest.mock import MagicMock, patch

import pytest

from azuredevops_timelog import azdo_client


@pytest.fixture(autouse=True)
def fake_pat(monkeypatch):
    # azdo_client.find_or_create_month_task exige AZDO_PAT definido; nos
    # testes isso nunca deve depender do ambiente real da máquina.
    monkeypatch.setenv("AZDO_PAT", "fake-token-for-tests")


def _mock_response(json_body, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_body
    resp.raise_for_status.return_value = None
    return resp


@patch("azuredevops_timelog.azdo_client.requests.get")
def test_find_or_create_month_task_returns_existing_id(mock_get):
    relations_response = _mock_response({
        "relations": [
            {"rel": "System.LinkTypes.Hierarchy-Forward",
             "url": "https://dev.azure.com/org/proj/_apis/wit/workItems/158687",
             "attributes": {"name": "Child"}},
            {"rel": "System.LinkTypes.Hierarchy-Reverse",
             "url": "https://dev.azure.com/org/proj/_apis/wit/workItems/82574",
             "attributes": {"name": "Parent"}},
        ]
    })
    ids_response = _mock_response({
        "value": [
            {"id": 158687, "fields": {"System.Title": "Automação - Julho/2026"}},
        ]
    })
    mock_get.side_effect = [relations_response, ids_response]

    task_id = azdo_client.find_or_create_month_task(2026, 7)

    assert task_id == 158687


@patch("azuredevops_timelog.azdo_client.requests.post")
@patch("azuredevops_timelog.azdo_client.requests.get")
def test_find_or_create_month_task_creates_when_missing(mock_get, mock_post):
    relations_response = _mock_response({"relations": []})
    mock_get.return_value = relations_response
    mock_post.return_value = _mock_response({"id": 999999}, status=201)

    task_id = azdo_client.find_or_create_month_task(2026, 8)

    assert task_id == 999999
    posted_body = mock_post.call_args.kwargs["json"]
    fields_set = {op["path"]: op["value"] for op in posted_body}
    assert fields_set["/fields/System.Title"] == "Automação - Agosto/2026"
    assert fields_set["/fields/Microsoft.VSTS.Common.Activity"] == "30-Desenvolvimento"
    assert fields_set["/fields/Microsoft.VSTS.Scheduling.OriginalEstimate"] == 168
    # Meia-noite LOCAL (offset -03:00 explícito), não meia-noite UTC — enviar
    # "Z" faz a UI mostrar o dia anterior às 21h (bug real encontrado na
    # primeira execução contra o Azure DevOps de verdade).
    assert fields_set["/fields/Microsoft.VSTS.Scheduling.StartDate"] == "2026-08-01T00:00:00-03:00"
    assert fields_set["/fields/Microsoft.VSTS.Scheduling.TargetDate"] == "2026-08-31T00:00:00-03:00"
    assert fields_set["/fields/Microsoft.VSTS.Scheduling.FinishDate"] == "2026-08-31T00:00:00-03:00"


@patch("azuredevops_timelog.azdo_client.requests.get")
def test_find_or_create_month_task_ignores_non_matching_titles(mock_get):
    relations_response = _mock_response({
        "relations": [
            {"rel": "System.LinkTypes.Hierarchy-Forward",
             "url": "https://dev.azure.com/org/proj/_apis/wit/workItems/1",
             "attributes": {"name": "Child"}},
        ]
    })
    ids_response = _mock_response({
        "value": [{"id": 1, "fields": {"System.Title": "Outra coisa"}}]
    })
    mock_get.side_effect = [relations_response, ids_response]

    with patch("azuredevops_timelog.azdo_client.requests.post") as mock_post:
        mock_post.return_value = _mock_response({"id": 42}, status=201)
        task_id = azdo_client.find_or_create_month_task(2026, 9)

    assert task_id == 42
```

- [ ] **Passo 2: Rodar e confirmar que falha**

Run: `cd F:\Automation && python -m pytest tests/test_azdo_client.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Passo 3: Implementar `azdo_client.py`**

```python
"""Cliente HTTP para a API REST oficial do Azure DevOps (autenticado por
PAT). Usado só para localizar/criar a Task mensal — nenhuma interação de
browser aqui, tudo via REST API documentada.
"""
from __future__ import annotations

import requests

from azuredevops_timelog import config
from azuredevops_timelog.dates import month_bounds, task_title_for


def _auth():
    return ("", config.azdo_pat())


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
    ANTERIOR às 21h na UI — bug real encontrado na primeira Task criada
    (168187, Agosto/2026: Start Date apareceu "31/07/2026 21:00" e Target
    Date "30/08/2026 21:00" em vez de 01/08 e 31/08). O formato certo leva
    o offset local explícito, não "Z".
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
```

Criar `F:\Automation\azuredevops_timelog\__init__.py` vazio (se ainda não existir da Task 1).

- [ ] **Passo 4: Rodar e confirmar que passa**

Run: `cd F:\Automation && python -m pytest tests/test_azdo_client.py -v`
Expected: PASS (3 testes)

- [ ] **Marcar como concluído**

---

### Task 4: `timelog_client.py` — ler/gravar entradas de horas via API interna da TimeLog (TDD)

**Files:**
- Create: `F:\Automation\azuredevops_timelog\timelog_client.py`
- Test: `F:\Automation\tests\test_timelog_client.py`

**Interfaces:**
- Consumes: `azuredevops_timelog.config.*`
- Produces: `get_entries(work_item_id: int) -> list[dict]`, `entry_exists_for_date(work_item_id: int, day: date) -> bool`, `add_time_log_entry(work_item_id: int, day: date, hours: int, dry_run: bool = False) -> dict`

- [ ] **Passo 1: Escrever os testes**

Criar `F:\Automation\tests\test_timelog_client.py`:

```python
from datetime import date
from unittest.mock import MagicMock, patch

from azuredevops_timelog import timelog_client

SAMPLE_ENTRY = {
    "timeLogId": "c9e4f09c-5922-490c-b00b-006fb518d478",
    "comment": None,
    "week": "2026-W31",
    "timeTypeDescription": "01-Projeto Padrão",
    "minutes": 240,
    "date": "2026-07-29",
    "userId": "<REDACTED - agora dinamico via azdo_client.get_current_user()>",
    "userName": "<REDACTED - agora dinamico via azdo_client.get_current_user()>",
    "userEmail": "<REDACTED - agora dinamico via azdo_client.get_current_user()>",
}


def _mock_response(json_body, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_body
    resp.raise_for_status.return_value = None
    return resp


@patch("azuredevops_timelog.timelog_client.requests.get")
def test_get_entries_sends_expected_headers(mock_get):
    mock_get.return_value = _mock_response([SAMPLE_ENTRY])

    result = timelog_client.get_entries(158687)

    assert result == [SAMPLE_ENTRY]
    _, kwargs = mock_get.call_args
    assert kwargs["headers"]["x-functions-key"]
    assert kwargs["headers"]["x-timelog-usermakingchange"] == "<REDACTED - agora dinamico via azdo_client.get_current_user()>"


@patch("azuredevops_timelog.timelog_client.requests.get")
def test_entry_exists_for_date_true_when_date_matches(mock_get):
    mock_get.return_value = _mock_response([SAMPLE_ENTRY])

    assert timelog_client.entry_exists_for_date(158687, date(2026, 7, 29)) is True


@patch("azuredevops_timelog.timelog_client.requests.get")
def test_entry_exists_for_date_false_when_no_match(mock_get):
    mock_get.return_value = _mock_response([SAMPLE_ENTRY])

    assert timelog_client.entry_exists_for_date(158687, date(2026, 8, 24)) is False


@patch("azuredevops_timelog.timelog_client.requests.post")
def test_add_time_log_entry_sends_minutes_and_type(mock_post):
    mock_post.return_value = _mock_response({"logsCreated": ["new-id"]}, status=201)

    result = timelog_client.add_time_log_entry(158687, date(2026, 8, 24), 4)

    assert result == {"logsCreated": ["new-id"]}
    args, kwargs = mock_post.call_args
    assert args[0] == "https://boznet-timelogapi.azurewebsites.net/api/40264be6-1998-420f-8cb2-0bdb5d42adf6/timelog"
    assert kwargs["json"]["minutes"] == 240
    assert kwargs["json"]["date"] == "2026-08-24"
    assert kwargs["json"]["timeTypeDescription"] == "01-Projeto Padrão"


@patch("azuredevops_timelog.timelog_client.requests.post")
def test_add_time_log_entry_dry_run_does_not_call_requests(mock_post):
    result = timelog_client.add_time_log_entry(158687, date(2026, 8, 24), 4, dry_run=True)

    mock_post.assert_not_called()
    assert result["minutes"] == 240
```

- [ ] **Passo 2: Rodar e confirmar que falha**

Run: `cd F:\Automation && python -m pytest tests/test_timelog_client.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Passo 3: Implementar `timelog_client.py`**

```python
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

_DATE_FMT = "%Y-%m-%d"


def _headers() -> dict:
    return {
        "accept": "application/json",
        "x-functions-key": config.TIMELOG_FUNCTIONS_KEY,
        "x-timelog-usermakingchange": config.TIMELOG_USER_NAME,
    }


def _workitem_url(work_item_id: int) -> str:
    return (
        f"{config.TIMELOG_API_BASE}/timelog/project/{config.PROJECT_ID}"
        f"/workitem/{work_item_id}"
    )


def get_entries(work_item_id: int) -> list[dict]:
    resp = requests.get(_workitem_url(work_item_id), headers=_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


def entry_exists_for_date(work_item_id: int, day: date) -> bool:
    target = day.strftime(_DATE_FMT)
    return any(entry["date"] == target for entry in get_entries(work_item_id))


def _add_url() -> str:
    return f"{config.TIMELOG_API_BASE}/timelog"


def add_time_log_entry(
    work_item_id: int, day: date, hours: int, dry_run: bool = False
) -> dict:
    body = {
        "workItemId": work_item_id,
        "projectId": config.PROJECT_ID,
        "date": day.strftime(_DATE_FMT),
        "minutes": hours * 60,
        "timeTypeDescription": config.TIMELOG_TYPE_DESCRIPTION,
        "comment": None,
        "userId": config.TIMELOG_USER_ID,
        "userName": config.TIMELOG_USER_NAME,
        "userEmail": config.TIMELOG_USER_EMAIL,
    }
    if dry_run:
        print(f"[dry-run] POST {_add_url()}")
        print(f"[dry-run] body: {body}")
        return body

    resp = requests.post(_add_url(), headers=_headers(), json=body, timeout=30)
    resp.raise_for_status()
    return resp.json()
```

- [ ] **Passo 4: Rodar e confirmar que passa**

Run: `cd F:\Automation && python -m pytest tests/test_timelog_client.py -v`
Expected: PASS (5 testes)

- [ ] **Marcar como concluído**

---

### Task 5: `cli.py` + ponto de entrada — orquestração completa

**Files:**
- Create: `F:\Automation\azuredevops_timelog\cli.py`
- Create: `F:\Automation\azuredevops_timelog.py`

**Interfaces:**
- Consumes: `azuredevops_timelog.dates.{business_days_in_range, parse_date_range}`, `azuredevops_timelog.azdo_client.find_or_create_month_task`, `azuredevops_timelog.timelog_client.{entry_exists_for_date, add_time_log_entry}`
- Produces: `main() -> None`

- [ ] **Passo 1: Implementar `cli.py`**

```python
"""CLI: orquestra o fluxo completo de log de horas no Azure DevOps."""
from __future__ import annotations

import argparse
from datetime import date

from azuredevops_timelog import azdo_client, timelog_client
from azuredevops_timelog.dates import business_days_in_range, parse_date_range

HOURS_PER_DAY = 4


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Loga horas diárias no Azure DevOps. Sem --from/--to, cobre "
            "retroativamente do dia 1 do mês atual até hoje, validando dia "
            "a dia o que já foi logado e preenchendo só o que falta."
        )
    )
    parser.add_argument("--from", dest="date_from", help="YYYY-MM-DD (início do range; sobrepõe o default do mês atual)")
    parser.add_argument("--to", dest="date_to", help="YYYY-MM-DD (fim do range; use junto com --from)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra a chamada que seria feita ao TimeLog, sem enviar",
    )
    return parser


def main() -> None:
    args = _build_arg_parser().parse_args()
    date_range = parse_date_range(args, today=date.today())
    days = business_days_in_range(date_range.start, date_range.end)

    if not days:
        print("Nenhum dia útil no range informado (fim de semana/feriado). Nada a fazer.")
        return

    logged, skipped, failed = [], [], []
    task_ids: dict[tuple[int, int], int] = {}

    for day in days:
        month_key = (day.year, day.month)
        if month_key not in task_ids:
            task_ids[month_key] = azdo_client.find_or_create_month_task(*month_key)
        task_id = task_ids[month_key]

        try:
            if timelog_client.entry_exists_for_date(task_id, day):
                skipped.append(day)
                continue
            timelog_client.add_time_log_entry(task_id, day, HOURS_PER_DAY, dry_run=args.dry_run)
            if not args.dry_run:
                logged.append(day)
        except Exception as exc:  # segue pros próximos dias em vez de abortar o lote
            print(f"Falhou em {day.isoformat()}: {exc}")
            failed.append(day)

    if args.dry_run:
        print("\n[dry-run] nenhuma chamada real foi enviada.")
    print("\nResumo:")
    print(f"  Logados: {len(logged)} -> {[d.isoformat() for d in logged]}")
    print(f"  Já existiam: {len(skipped)} -> {[d.isoformat() for d in skipped]}")
    print(f"  Falharam: {len(failed)} -> {[d.isoformat() for d in failed]}")
```

- [ ] **Passo 2: Implementar o ponto de entrada raiz**

```python
"""Ponto de entrada: python azuredevops_timelog.py [--from YYYY-MM-DD --to YYYY-MM-DD] [--dry-run]"""
from azuredevops_timelog.cli import main

if __name__ == "__main__":
    main()
```

- [ ] **Passo 3: Validar (dry-run, dia atual)**

```powershell
$env:AZDO_PAT = "<seu token>"   # se ainda não definiu na sessão
cd F:\Automation
python azuredevops_timelog.py --dry-run
```

Expected: localiza ou cria a Task do mês atual (chamada real à API oficial — isso já cria a Task de verdade se não existir, mesmo em `--dry-run`; só o lançamento de horas em si fica em modo simulado), imprime `[dry-run] POST ...` e `[dry-run] body: {...}` (ou o aviso de fim de semana/feriado se for o caso).

- [ ] **Marcar como concluído**

---

### Task 6: Validação ponta a ponta (primeira execução real)

**Files:** nenhum (checklist de validação real — é aqui que o formato inferido do POST do TimeLog se confirmou).

**✅ Executada em 24/08/2026.** Resultado real, pra referência:

- [x] **Passo 1:** `--dry-run` localizou/criou a Task "Automação - Agosto/2026" (ID 168187) com os campos certos (confirmado via GET na API oficial: Activity=30-Desenvolvimento, Estimate=168, Start=01/08 00:00, Target=31/08 00:00) e imprimiu o body planejado.
- [x] **Passo 2:** primeira chamada real deu **400** — `"'Time Type Description' must not be empty."` — revelou que o campo certo é `timeTypeDescription`, não `timeTypeId`, e (via sondagem de rotas) que a URL certa é `{base}/timelog` sem `/project/{id}/workitem/{id}`. Ajustado em `timelog_client.py`; a chamada seguinte deu **201** com `{"logsCreated": ["406f12d8-..."]}`.
- [x] **Passo 3:** GET no work item 168187 confirmou a entrada: `4h, 2026-08-24, 01-Projeto Padrão`.
- [x] **Passo 4:** rodou de novo no mesmo dia → resumo mostrou "já existia" (1), sem duplicar.
- [x] **Passo 5:** backfill `--from 2026-08-20 --to 2026-08-24` → logou 20 e 21 (qui/sex), puland fim de semana (22/23) automaticamente, e 24 apareceu como "já existia".
- [x] **Marcar como concluído — Fase 1 pronta para uso diário manual.**

**Nota sobre o PAT:** o primeiro PAT gerado pelo usuário voltava `302` (redirect de login) em qualquer chamada, mesmo com escopo "Full access" e org certa — gerar um PAT novo resolveu (causa exata não isolada; não era bloqueio de Conditional Access da Petrobras, como se suspeitou inicialmente). Se acontecer de novo, gerar um token novo antes de investigar mais a fundo.

---

### Task 7: Ajustes pós-produção (feedback do usuário, 24/08/2026)

Depois da Task 6 validada, o usuário pediu dois ajustes a mais, vistos ao vivo contra a Task real 168187 (Agosto/2026):

1. **Datas erradas na UI:** Start Date apareceu "31/07/2026 21:00" e Target Date "30/08/2026 21:00" em vez de "01/08" e "31/08" — bug de fuso: `T00:00:00Z` é meia-noite UTC, que em BRT (UTC-3) cai às 21h do dia anterior. Corrigido enviando o offset local explícito (`-03:00`) em vez de `Z`. Também passou a preencher **Finish Date** já na criação (igual ao Target Date, último dia do mês) — o usuário pediu os três campos preenchidos desde o início, diferente do padrão histórico (Finish Date só era setado quando a Task fechava).
2. **Preenchimento retroativo automático:** o default do script (sem `--from`/`--to`) passou de "só hoje" para "do dia 1 do mês atual até hoje", validando dia a dia (`entry_exists_for_date`) e preenchendo só o que falta — sem precisar passar `--from`/`--to` manualmente todo santo dia. Dias úteis já continuavam pulando fim de semana/feriado nacional (`is_business_day`), isso não mudou, só passou a valer automaticamente pro mês inteiro.

**Files:**
- Modify: `F:\Automation\azuredevops_timelog\config.py` (`LOCAL_UTC_OFFSET = "-03:00"`)
- Modify: `F:\Automation\azuredevops_timelog\azdo_client.py` (`_local_midnight()`, `FinishDate` no patch de criação)
- Modify: `F:\Automation\azuredevops_timelog\dates.py` (`parse_date_range` — default vira mês inteiro)
- Modify: `F:\Automation\tests\test_azdo_client.py`, `F:\Automation\tests\test_dates.py`

- [x] **Passo 1:** adicionar `LOCAL_UTC_OFFSET = "-03:00"` em `config.py`.
- [x] **Passo 2:** `azdo_client.py` — função `_local_midnight(day)` retornando `f"{day.isoformat()}T00:00:00{config.LOCAL_UTC_OFFSET}"`; usar em Start/Target/Finish Date na criação da Task.
- [x] **Passo 3:** `dates.py` — `parse_date_range` sem `--from`/`--to` retorna `DateRange(month_bounds(today.year, today.month)[0], today)` em vez de `DateRange(today, today)`.
- [x] **Passo 4:** corrigir a Task 168187 já criada via PATCH direto na API (Start/Target/Finish Date) — feito ao vivo, não precisa repetir pra Tasks futuras (essas já nascem certas).
- [x] **Passo 5:** rodar os testes (23/23) e validar contra o Azure DevOps real — `--dry-run` mostrou os 13 dias úteis faltantes de agosto (03-07, 10-14, 17-19), rodado de verdade logou os 13 sem tocar nos 3 que já existiam (20, 21, 24), e rodar de novo confirmou 16/16 "já existiam".
- [x] **Marcar como concluído.**

---

### Task 8: Fechar a Task do mês anterior + agendamento automático (feedback do usuário, 24/08/2026)

Dois pedidos a mais, ambos concluídos:

1. **Fechar a Task do mês anterior automaticamente.** Testado ao vivo contra uma Task descartável: `System.State` aceita ir direto de `New` pra `Closed` via API (`200`, sem precisar passar por `Ativo` no meio — a Reason automática vem como `"Completed"` em vez do `"Moved out of state Ativo"` do padrão histórico manual, cosmético, sem efeito prático). `close_previous_month_task(year, month)` em `azdo_client.py`: acha a Task do mês anterior a `(year, month)` pelo título, só fecha se existir e não estiver `Closed` ainda; **não cria** a Task do mês anterior se ela nunca existiu. Chamado uma vez por execução em `cli.py`, antes do loop de dias — idempotente, seguro rodar todo dia.
2. **Agendamento automático (Fase 2, decidida entrar em escopo agora).** Windows Task Scheduler, tarefa `AzureDevOpsTimeLog`, dispara `F:\Automation\run_azuredevops_timelog.ps1` toda seg-sex às 18:30, rodando como o usuário atual (usa o `AZDO_PAT` já persistido via `setx`). Saída vai pra `F:\Automation\logs\azuredevops_timelog.log` (o wrapper precisou de `[Console]::OutputEncoding` + `$env:PYTHONIOENCODING=utf-8` + `Out-File -Encoding utf8` pra não corromper os acentos — sem isso o log saía ilegível). Testado disparando manualmente 2x (`Start-ScheduledTask`), `LastTaskResult = 0` nas duas.

**Files:**
- Modify: `F:\Automation\azuredevops_timelog\dates.py` (`previous_month(year, month) -> (int, int)`)
- Modify: `F:\Automation\azuredevops_timelog\azdo_client.py` (`_get_state`, `_set_state`, `close_previous_month_task`)
- Modify: `F:\Automation\azuredevops_timelog\cli.py` (chama `close_previous_month_task` antes do loop)
- Modify: `F:\Automation\tests\test_dates.py`, `F:\Automation\tests\test_azdo_client.py`
- Create: `F:\Automation\run_azuredevops_timelog.ps1` (wrapper pro Task Scheduler)
- Create (runtime): `F:\Automation\logs\azuredevops_timelog.log`

```python
# dates.py — acrescentar
def previous_month(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return year - 1, 12
    return year, month - 1
```

```python
# azdo_client.py — acrescentar (depois de find_or_create_month_task)
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
```

```python
# cli.py — no início de main(), antes do "if not days:"
today = date.today()
date_range = parse_date_range(args, today=today)
days = business_days_in_range(date_range.start, date_range.end)

closed_id = azdo_client.close_previous_month_task(today.year, today.month)
if closed_id is not None:
    print(f"Task do mês anterior fechada automaticamente (ID {closed_id}).")
```

```powershell
# F:\Automation\run_azuredevops_timelog.ps1
$ErrorActionPreference = "Continue"

$root = "F:\Automation"
$logDir = Join-Path $root "logs"
$logFile = Join-Path $logDir "azuredevops_timelog.log"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $logFile -Value "`n=== $timestamp ==="

Set-Location $root
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
python azuredevops_timelog.py 2>&1 | Out-File -FilePath $logFile -Append -Encoding utf8
```

```powershell
# Registro único no Task Scheduler (já executado nesta sessão)
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument '-NoProfile -ExecutionPolicy Bypass -File "F:\Automation\run_azuredevops_timelog.ps1"'
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 18:30
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd
Register-ScheduledTask -TaskName "AzureDevOpsTimeLog" -Action $action -Trigger $trigger -Settings $settings -Description "Loga 4h diarias no Azure DevOps (PBI Automacao) - script pessoal" -Force
```

**Risco conhecido, não coberto por código:** quando o PAT expirar (validade escolhida na criação), a tarefa agendada vai falhar silenciosamente — o único sinal é o erro gravado em `F:\Automation\logs\azuredevops_timelog.log`. Renovar o PAT continua manual (gerar um novo em `_usersSettings/tokens` e rodar `setx AZDO_PAT "<novo>"` de novo). Vale checar o log de vez em quando.

- [x] **Marcar como concluído.**

---

## Fora de escopo (decidido explicitamente, não esquecido)

- Agendamento automático (Task Scheduler / cron) — Fase 2, a decidir depois que a Fase 1 estiver validada em uso real. Fica mais simples agora: sem browser, é só um `schtasks` chamando o script.
- Fechar a Task no fim do mês — continua manual, como hoje.
- Feriados móveis / pontos facultativos específicos da Petrobras — só feriados nacionais fixos via lib `holidays`.
- Renovar o PAT quando expirar — fora do escopo do script, é uma ação manual sua (gerar um novo em `_usersSettings/tokens`).

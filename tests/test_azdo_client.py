from unittest.mock import MagicMock, patch

import pytest

from azuredevops_timelog import azdo_client


@pytest.fixture(autouse=True)
def fake_pat(monkeypatch):
    # azdo_client.find_or_create_month_task exige AZDO_PAT definido; nos
    # testes isso nunca deve depender do ambiente real da máquina.
    monkeypatch.setenv("AZDO_PAT", "fake-token-for-tests")
    # get_current_user cacheia em memória (global do módulo) — sem
    # resetar aqui, um teste anterior "vaza" o usuário fake pros
    # seguintes, mascarando bugs reais.
    azdo_client._cached_user = None


def _mock_response(json_body, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_body
    resp.raise_for_status.return_value = None
    return resp


@patch("azuredevops_timelog.azdo_client.requests.get")
def test_get_current_user_reads_from_connection_data(mock_get):
    mock_get.return_value = _mock_response({
        "authenticatedUser": {
            "id": "00000000-0000-0000-0000-000000000001",
            "customDisplayName": "Jane Doe",
            "properties": {"Account": {"$type": "System.String", "$value": "jane.doe@example.com"}},
        }
    })

    user = azdo_client.get_current_user()

    assert user.id == "00000000-0000-0000-0000-000000000001"
    assert user.name == "Jane Doe"
    assert user.email == "jane.doe@example.com"


@patch("azuredevops_timelog.azdo_client.requests.get")
def test_get_current_user_is_cached_across_calls(mock_get):
    mock_get.return_value = _mock_response({
        "authenticatedUser": {
            "id": "00000000-0000-0000-0000-000000000001",
            "customDisplayName": "Jane Doe",
            "properties": {"Account": {"$type": "System.String", "$value": "jane.doe@example.com"}},
        }
    })

    azdo_client.get_current_user()
    azdo_client.get_current_user()

    assert mock_get.call_count == 1


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


@patch("azuredevops_timelog.azdo_client.requests.patch")
@patch("azuredevops_timelog.azdo_client.requests.get")
def test_close_previous_month_task_closes_open_task(mock_get, mock_patch):
    relations_response = _mock_response({
        "relations": [
            {"rel": "System.LinkTypes.Hierarchy-Forward",
             "url": "https://dev.azure.com/org/proj/_apis/wit/workItems/158687",
             "attributes": {"name": "Child"}},
        ]
    })
    ids_response = _mock_response({
        "value": [{"id": 158687, "fields": {"System.Title": "Automação - Julho/2026"}}]
    })
    state_response = _mock_response({"fields": {"System.State": "New"}})
    mock_get.side_effect = [relations_response, ids_response, state_response]
    mock_patch.return_value = _mock_response({"fields": {"System.State": "Closed"}})

    closed_id = azdo_client.close_previous_month_task(2026, 8)

    assert closed_id == 158687
    posted_patch = mock_patch.call_args.kwargs["json"]
    assert posted_patch == [{"op": "add", "path": "/fields/System.State", "value": "Closed"}]


@patch("azuredevops_timelog.azdo_client.requests.get")
def test_close_previous_month_task_skips_when_already_closed(mock_get):
    relations_response = _mock_response({
        "relations": [
            {"rel": "System.LinkTypes.Hierarchy-Forward",
             "url": "https://dev.azure.com/org/proj/_apis/wit/workItems/158687",
             "attributes": {"name": "Child"}},
        ]
    })
    ids_response = _mock_response({
        "value": [{"id": 158687, "fields": {"System.Title": "Automação - Julho/2026"}}]
    })
    state_response = _mock_response({"fields": {"System.State": "Closed"}})
    mock_get.side_effect = [relations_response, ids_response, state_response]

    with patch("azuredevops_timelog.azdo_client.requests.patch") as mock_patch:
        closed_id = azdo_client.close_previous_month_task(2026, 8)

    assert closed_id is None
    mock_patch.assert_not_called()


@patch("azuredevops_timelog.azdo_client.requests.get")
def test_close_previous_month_task_does_nothing_when_task_never_existed(mock_get):
    relations_response = _mock_response({"relations": []})
    mock_get.return_value = relations_response

    with patch("azuredevops_timelog.azdo_client.requests.patch") as mock_patch:
        closed_id = azdo_client.close_previous_month_task(2026, 1)  # fecha Dez/2025

    assert closed_id is None
    mock_patch.assert_not_called()

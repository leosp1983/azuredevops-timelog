from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from azuredevops_timelog import timelog_client
from azuredevops_timelog.azdo_client import CurrentUser

FAKE_USER = CurrentUser(
    id="00000000-0000-0000-0000-000000000001",
    name="Jane Doe",
    email="jane.doe@example.com",
)

OTHER_USER_ENTRY = {
    "timeLogId": "c9e4f09c-5922-490c-b00b-006fb518d478",
    "comment": None,
    "week": "2026-W31",
    "timeTypeDescription": "01-Projeto Padrão",
    "minutes": 240,
    "date": "2026-07-29",
    "userId": "00000000-0000-0000-0000-000000000002",
    "userName": "John Smith",
    "userEmail": "john.smith@example.com",
}

FAKE_USER_ENTRY = {
    "timeLogId": "406f12d8-6ec4-4c70-9c82-a2990eb5a7ed",
    "comment": None,
    "week": "2026-W31",
    "timeTypeDescription": "01-Projeto Padrão",
    "minutes": 240,
    "date": "2026-07-29",
    "userId": FAKE_USER.id,
    "userName": FAKE_USER.name,
    "userEmail": FAKE_USER.email,
}


@pytest.fixture(autouse=True)
def fake_timelog_key(monkeypatch):
    monkeypatch.setenv("TIMELOG_FUNCTIONS_KEY", "fake-key-for-tests")


def _mock_response(json_body, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_body
    resp.raise_for_status.return_value = None
    return resp


@patch("azuredevops_timelog.timelog_client.requests.get")
def test_get_entries_sends_expected_headers(mock_get):
    mock_get.return_value = _mock_response([FAKE_USER_ENTRY])

    result = timelog_client.get_entries(158687, FAKE_USER)

    assert result == [FAKE_USER_ENTRY]
    _, kwargs = mock_get.call_args
    assert kwargs["headers"]["x-functions-key"]
    assert kwargs["headers"]["x-timelog-usermakingchange"] == FAKE_USER.name


@patch("azuredevops_timelog.timelog_client.requests.get")
def test_entry_exists_for_date_true_when_own_entry_matches(mock_get):
    mock_get.return_value = _mock_response([FAKE_USER_ENTRY])

    assert timelog_client.entry_exists_for_date(158687, date(2026, 7, 29), FAKE_USER) is True


@patch("azuredevops_timelog.timelog_client.requests.get")
def test_entry_exists_for_date_false_when_no_match(mock_get):
    mock_get.return_value = _mock_response([FAKE_USER_ENTRY])

    assert timelog_client.entry_exists_for_date(158687, date(2026, 8, 24), FAKE_USER) is False


@patch("azuredevops_timelog.timelog_client.requests.get")
def test_entry_exists_for_date_ignores_other_users_entries(mock_get):
    # Task compartilhada pelo time: o lançamento de outra pessoa no mesmo
    # dia não pode contar como "já existe" pra quem está rodando agora.
    mock_get.return_value = _mock_response([OTHER_USER_ENTRY])

    assert timelog_client.entry_exists_for_date(158687, date(2026, 7, 29), FAKE_USER) is False


@patch("azuredevops_timelog.timelog_client.requests.post")
def test_add_time_log_entry_sends_minutes_type_and_user(mock_post):
    mock_post.return_value = _mock_response({"logsCreated": ["new-id"]}, status=201)

    result = timelog_client.add_time_log_entry(158687, date(2026, 8, 24), 4, FAKE_USER)

    assert result == {"logsCreated": ["new-id"]}
    args, kwargs = mock_post.call_args
    assert args[0] == "https://boznet-timelogapi.azurewebsites.net/api/40264be6-1998-420f-8cb2-0bdb5d42adf6/timelog"
    assert kwargs["json"]["minutes"] == 240
    assert kwargs["json"]["date"] == "2026-08-24"
    assert kwargs["json"]["timeTypeDescription"] == "01-Projeto Padrão"
    assert kwargs["json"]["userId"] == FAKE_USER.id
    assert kwargs["json"]["userName"] == FAKE_USER.name
    assert kwargs["json"]["userEmail"] == FAKE_USER.email


@patch("azuredevops_timelog.timelog_client.requests.post")
def test_add_time_log_entry_dry_run_does_not_call_requests(mock_post):
    result = timelog_client.add_time_log_entry(
        158687, date(2026, 8, 24), 4, FAKE_USER, dry_run=True
    )

    mock_post.assert_not_called()
    assert result["minutes"] == 240

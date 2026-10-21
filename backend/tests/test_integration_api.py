import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.main import app
from app.models.meeting_status import MeetingStatus
from app.models.integration_delivery import IntegrationDeliveryStatus

client = TestClient(app)

BASE_URL = "/meetings"

@patch("app.api.v1.integrations.get_enabled_providers", return_value=["discord", "notion"])
@patch("app.api.v1.integrations.MeetingRepository")
@patch("app.api.v1.integrations.IntegrationDeliveryRepository")
@patch("app.api.v1.integrations.enqueue_integration_delivery")
def test_retry_integrations_enqueues_task_and_returns_202(
    mock_enqueue, mock_delivery_repo_class, mock_meeting_repo_class, mock_enabled_providers
):
    # Setup da reunião simulada (Mock do banco de dados)
    mock_meeting = MagicMock()
    mock_meeting.status = MeetingStatus.COMPLETED
    mock_meeting_repo_class.return_value.get_by_id.return_value = mock_meeting

    # Setup dos providers simulados com os seus status
    mock_delivery_repo_class.return_value.list_by_meeting.return_value = [
        MagicMock(provider="notion", status=IntegrationDeliveryStatus.FAILED.value),
        MagicMock(provider="discord", status=IntegrationDeliveryStatus.SUCCESS.value)
    ]

    response = client.post(
        f"{BASE_URL}/1/integrations/retry", 
        json={"providers": ["notion", "discord"]}
    )

    assert response.status_code == 202
    assert response.json() == {"meeting_id": 1, "providers": ["notion"]}
    
    # Verifica se a task em background foi chamada corretamente só com o Notion
    mock_enqueue.assert_called_once()
    args, kwargs = mock_enqueue.call_args
    assert args[0] == 1  # meeting_id
    assert kwargs["providers"] == ["notion"]
    assert kwargs["reset"] is False

@patch("app.api.v1.integrations.MeetingRepository")
def test_retry_integrations_rejects_in_progress_meeting(mock_meeting_repo_class):
    # Setup de uma reunião ainda não concluída
    mock_meeting = MagicMock()
    mock_meeting.status = MeetingStatus.PROCESSING
    mock_meeting_repo_class.return_value.get_by_id.return_value = mock_meeting

    # Chamada POST corrigida
    response = client.post(f"{BASE_URL}/1/integrations/retry")

    assert response.status_code == 409
    assert "não foi concluída" in response.json()["detail"]

@patch("app.api.v1.integrations.MeetingRepository")
def test_list_integrations_returns_delivery_status(mock_meeting_repo_class):
    # Setup forçando a não encontrar nenhuma reunião
    mock_meeting_repo_class.return_value.get_by_id.return_value = None

    # Chamada POST corrigida (testando um ID que não existe)
    response = client.post(f"{BASE_URL}/999/integrations/retry")

    assert response.status_code == 404
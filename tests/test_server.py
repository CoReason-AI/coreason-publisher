# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_publisher

from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from coreason_publisher.core.orchestrator import PublisherOrchestrator
from coreason_publisher.server import app


@pytest.fixture  # type: ignore[misc]
def mock_orchestrator() -> MagicMock:
    orchestrator = MagicMock(spec=PublisherOrchestrator)
    # Setup default mock behaviors
    orchestrator.git_lfs = MagicMock()
    orchestrator.git_lfs.is_installed.return_value = True
    orchestrator.git_lfs.is_initialized.return_value = True
    orchestrator.git_provider = MagicMock()
    orchestrator.git_provider.gl = MagicMock()
    orchestrator.workspace_path = Path("/tmp/test_workspace")
    return orchestrator


@pytest.fixture  # type: ignore[misc]
def client(mock_orchestrator: MagicMock) -> Generator[TestClient, None, None]:
    # Patch get_server_orchestrator to return our mock
    with patch("coreason_publisher.server.get_server_orchestrator", return_value=mock_orchestrator):
        with TestClient(app) as c:
            yield c


def test_propose_success(client: TestClient, mock_orchestrator: MagicMock) -> None:
    payload = {
        "project_id": "proj-123",
        "draft_id": "draft-456",
        "bump_type": "patch",
        "user_id": "user-789",
        "description": "test description",
    }
    response = client.post("/propose", json=payload)
    assert response.status_code == 200
    assert response.json() == {"status": "success", "message": "Release proposal submitted successfully"}
    mock_orchestrator.propose_release.assert_called_once()


def test_propose_failure_400(client: TestClient, mock_orchestrator: MagicMock) -> None:
    mock_orchestrator.propose_release.side_effect = ValueError("Invalid bump type")
    payload = {
        "project_id": "proj-123",
        "draft_id": "draft-456",
        "bump_type": "patch",
        "user_id": "user-789",
        "description": "test description",
    }
    response = client.post("/propose", json=payload)
    assert response.status_code == 400
    assert "Invalid bump type" in response.json()["detail"]


def test_propose_failure_502(client: TestClient, mock_orchestrator: MagicMock) -> None:
    mock_orchestrator.propose_release.side_effect = RuntimeError("GitLab error")
    payload = {
        "project_id": "proj-123",
        "draft_id": "draft-456",
        "bump_type": "patch",
        "user_id": "user-789",
        "description": "test description",
    }
    response = client.post("/propose", json=payload)
    assert response.status_code == 502
    assert "GitLab error" in response.json()["detail"]


def test_release_success(client: TestClient, mock_orchestrator: MagicMock) -> None:
    payload = {"mr_id": 123, "srb_signature": "sig-abc", "srb_user_id": "srb-user"}
    response = client.post("/release", json=payload)
    assert response.status_code == 200
    mock_orchestrator.finalize_release.assert_called_once()


def test_reject_success(client: TestClient, mock_orchestrator: MagicMock) -> None:
    payload = {"mr_id": 123, "draft_id": "draft-456", "reason": "bad code"}
    response = client.post("/reject", json=payload)
    assert response.status_code == 200
    mock_orchestrator.reject_release.assert_called_once()


def test_health_success(client: TestClient, mock_orchestrator: MagicMock) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_health_failure_lfs(client: TestClient, mock_orchestrator: MagicMock) -> None:
    mock_orchestrator.git_lfs.is_installed.return_value = False
    response = client.get("/health")
    assert response.status_code == 503
    assert "Git LFS not installed" in response.json()["detail"]

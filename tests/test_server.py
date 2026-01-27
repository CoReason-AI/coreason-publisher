# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_publisher

from unittest.mock import MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from coreason_publisher.server import app


@pytest.fixture
def mock_orchestrator():
    orchestrator = MagicMock()
    orchestrator.workspace_path = "dummy_path"
    return orchestrator


@pytest.fixture
def client(mock_orchestrator):
    with patch("coreason_publisher.server.get_orchestrator", return_value=mock_orchestrator):
        with TestClient(app) as c:
            yield c


def test_health_check(client, mock_orchestrator):
    mock_orchestrator.git_lfs.is_initialized.return_value = True
    # mock_orchestrator.git_provider is a MagicMock, so access to .gl.auth() works fine

    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "healthy", "lfs": "ok", "gitlab": "connected"}

def test_health_check_failure(client, mock_orchestrator):
    mock_orchestrator.git_lfs.is_initialized.return_value = False

    response = client.get("/health")
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


def test_propose_release_success(client, mock_orchestrator):
    payload = {
        "project_id": "proj-123",
        "draft_id": "draft-456",
        "bump_type": "patch",
        "user_id": "user-789",
        "description": "Test release"
    }
    response = client.post("/propose", json=payload)
    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.json()["status"] == "success"

    mock_orchestrator.propose_release.assert_called_once_with(
        project_id="proj-123",
        foundry_draft_id="draft-456",
        bump_type="patch",
        sre_user_id="user-789",
        release_description="Test release"
    )

def test_propose_release_bad_request(client, mock_orchestrator):
    mock_orchestrator.propose_release.side_effect = ValueError("Invalid input")
    payload = {
        "project_id": "proj-123",
        "draft_id": "draft-456",
        "bump_type": "patch",
        "user_id": "user-789",
        "description": "Test release"
    }
    response = client.post("/propose", json=payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST

def test_release_success(client, mock_orchestrator):
    payload = {
        "mr_id": 101,
        "srb_signature": "sig-abc",
        "srb_user_id": "srb-user"
    }
    response = client.post("/release", json=payload)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "success"

    mock_orchestrator.finalize_release.assert_called_once_with(
        mr_id=101,
        srb_signature="sig-abc",
        srb_user_id="srb-user"
    )

def test_reject_success(client, mock_orchestrator):
    payload = {
        "mr_id": 101,
        "draft_id": "draft-456",
        "reason": "Not good enough"
    }
    response = client.post("/reject", json=payload)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "success"

    mock_orchestrator.reject_release.assert_called_once_with(
        mr_id=101,
        draft_id="draft-456",
        reason="Not good enough"
    )

# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_publisher

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from coreason_publisher.server import app


@pytest.fixture
def mock_orchestrator() -> MagicMock:
    orchestrator = MagicMock()
    # Setup LFS check for health endpoint
    orchestrator.git_lfs.is_initialized.return_value = True
    return orchestrator


@pytest.fixture
def client(mock_orchestrator: MagicMock) -> Generator[TestClient, Any, None]:
    # Patch get_orchestrator used in lifespan to return our mock
    with patch("coreason_publisher.server.get_orchestrator", return_value=mock_orchestrator):
        with TestClient(app) as client:
            yield client


def test_health_check_success(client: TestClient, mock_orchestrator: MagicMock) -> None:
    mock_orchestrator.git_provider.get_last_tag.return_value = "v1.0.0"
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
    mock_orchestrator.git_lfs.is_initialized.assert_called_once()
    mock_orchestrator.git_provider.get_last_tag.assert_called_once()


def test_health_check_lfs_failure(client: TestClient, mock_orchestrator: MagicMock) -> None:
    mock_orchestrator.git_lfs.is_initialized.return_value = False
    response = client.get("/health")
    assert response.status_code == 503
    assert "Git LFS" in response.json()["detail"]


def test_health_check_provider_failure(client: TestClient, mock_orchestrator: MagicMock) -> None:
    mock_orchestrator.git_provider.get_last_tag.side_effect = RuntimeError("Auth failed")
    response = client.get("/health")
    assert response.status_code == 503
    assert "Git Provider check failed" in response.json()["detail"]


def test_propose_release_success(client: TestClient, mock_orchestrator: MagicMock) -> None:
    payload = {
        "project_id": "proj-1",
        "draft_id": "draft-1",
        "bump_type": "patch",
        "user_id": "user-1",
        "description": "desc",
    }
    response = client.post("/propose", json=payload)
    assert response.status_code == 202
    mock_orchestrator.propose_release.assert_called_once_with(
        project_id="proj-1",
        foundry_draft_id="draft-1",
        bump_type="patch",
        sre_user_id="user-1",
        release_description="desc",
    )


def test_propose_release_failure(client: TestClient, mock_orchestrator: MagicMock) -> None:
    mock_orchestrator.propose_release.side_effect = RuntimeError("GitLab error")
    payload = {
        "project_id": "proj-1",
        "draft_id": "draft-1",
        "bump_type": "patch",
        "user_id": "user-1",
        "description": "desc",
    }
    response = client.post("/propose", json=payload)
    assert response.status_code == 502
    assert "GitLab error" in response.json()["detail"]


def test_finalize_release_success(client: TestClient, mock_orchestrator: MagicMock) -> None:
    payload = {"mr_id": 123, "srb_signature": "sig", "srb_user_id": "user-2"}
    response = client.post("/release", json=payload)
    assert response.status_code == 200
    mock_orchestrator.finalize_release.assert_called_once_with(mr_id=123, srb_signature="sig", srb_user_id="user-2")


def test_finalize_release_bad_request(client: TestClient, mock_orchestrator: MagicMock) -> None:
    mock_orchestrator.finalize_release.side_effect = ValueError("Invalid signature")
    payload = {"mr_id": 123, "srb_signature": "sig", "srb_user_id": "user-2"}
    response = client.post("/release", json=payload)
    assert response.status_code == 400
    assert "Invalid signature" in response.json()["detail"]


def test_reject_release_success(client: TestClient, mock_orchestrator: MagicMock) -> None:
    payload = {"mr_id": 123, "draft_id": "draft-1", "reason": "bad code"}
    response = client.post("/reject", json=payload)
    assert response.status_code == 200
    mock_orchestrator.reject_release.assert_called_once_with(mr_id=123, draft_id="draft-1", reason="bad code")

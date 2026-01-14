# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_publisher

import os
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from coreason_publisher.core.gitlab_provider import GitLabProvider
from coreason_publisher.core.orchestrator import PublisherOrchestrator
from coreason_publisher.core.version_manager import BumpType
from coreason_publisher.main import app, get_orchestrator, main
from typer import Exit
from typer.testing import CliRunner

runner = CliRunner()


@pytest.fixture  # type: ignore[misc]
def mock_orchestrator() -> Generator[MagicMock, None, None]:
    with patch("coreason_publisher.main.get_orchestrator") as mock_get:
        mock_orch_instance = MagicMock(spec=PublisherOrchestrator)
        mock_get.return_value = mock_orch_instance
        yield mock_orch_instance


def test_propose_command(mock_orchestrator: MagicMock) -> None:
    """Test the propose command calls the orchestrator correctly."""
    result = runner.invoke(
        app,
        [
            "propose",
            "--project-id",
            "proj-1",
            "--draft-id",
            "draft-1",
            "--bump",
            "minor",
            "--user-id",
            "sre-1",
            "--description",
            "test release",
        ],
    )

    assert result.exit_code == 0
    assert "Release proposal submitted successfully" in result.stdout

    mock_orchestrator.propose_release.assert_called_once()
    call_kwargs = mock_orchestrator.propose_release.call_args.kwargs
    assert call_kwargs["project_id"] == "proj-1"
    assert call_kwargs["foundry_draft_id"] == "draft-1"
    # When passed from Typer, it comes as the Enum member
    assert call_kwargs["bump_type"] == BumpType.MINOR
    assert call_kwargs["sre_user_id"] == "sre-1"
    assert call_kwargs["release_description"] == "test release"


def test_propose_command_failure(mock_orchestrator: MagicMock) -> None:
    """Test the propose command handles exceptions."""
    mock_orchestrator.propose_release.side_effect = RuntimeError("Something went wrong")

    result = runner.invoke(
        app, ["propose", "--project-id", "proj-1", "--draft-id", "draft-1", "--bump", "patch", "--user-id", "u"]
    )

    assert result.exit_code == 1
    assert "Error: Something went wrong" in result.stdout


def test_release_command(mock_orchestrator: MagicMock) -> None:
    """Test the release command calls the orchestrator correctly."""
    result = runner.invoke(app, ["release", "--mr-id", "123", "--signature", "valid-sig", "--srb-user-id", "srb-1"])

    assert result.exit_code == 0
    assert "Release finalized successfully" in result.stdout

    mock_orchestrator.finalize_release.assert_called_once_with(
        mr_id=123, srb_signature="valid-sig", srb_user_id="srb-1"
    )


def test_release_command_failure(mock_orchestrator: MagicMock) -> None:
    """Test the release command handles exceptions."""
    mock_orchestrator.finalize_release.side_effect = ValueError("Invalid signature")

    result = runner.invoke(app, ["release", "--mr-id", "123", "--signature", "bad-sig", "--srb-user-id", "srb-1"])

    assert result.exit_code == 1
    assert "Error: Invalid signature" in result.stdout


def test_reject_command(mock_orchestrator: MagicMock) -> None:
    """Test the reject command calls the orchestrator correctly."""
    result = runner.invoke(
        app,
        ["reject", "--mr-id", "123", "--draft-id", "draft-1", "--reason", "bad code"],
    )

    assert result.exit_code == 0
    assert "Release rejected successfully" in result.stdout

    mock_orchestrator.reject_release.assert_called_once_with(mr_id=123, draft_id="draft-1", reason="bad code")


def test_reject_command_failure(mock_orchestrator: MagicMock) -> None:
    """Test the reject command handles exceptions."""
    mock_orchestrator.reject_release.side_effect = RuntimeError("Failed to reject")

    result = runner.invoke(
        app,
        ["reject", "--mr-id", "123", "--draft-id", "draft-1", "--reason", "fail"],
    )

    assert result.exit_code == 1
    assert "Error: Failed to reject" in result.stdout


def test_get_orchestrator_success(tmp_path: Path) -> None:
    """Test successful initialization of orchestrator."""
    env_vars = {
        "GITLAB_TOKEN": "token",
        "ASSAY_API_URL": "http://assay.com",
        "ASSAY_API_TOKEN": "assay-token",
        "FOUNDRY_API_URL": "http://foundry.com",
        "FOUNDRY_API_TOKEN": "foundry-token",
        "GITLAB_PROJECT_ID": "100",
    }

    with patch.dict(os.environ, env_vars):
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            with patch("coreason_publisher.main.GitLocal"):
                with patch("coreason_publisher.main.GitLFS"):
                    orch = get_orchestrator()
                    assert isinstance(orch, PublisherOrchestrator)
                    assert isinstance(orch.git_provider, GitLabProvider)
                    assert orch.git_provider.project_id == "100"


def test_get_orchestrator_fallback_project_id(tmp_path: Path) -> None:
    """Test initialization when GITLAB_PROJECT_ID is missing (fallback)."""
    env_vars = {
        "GITLAB_TOKEN": "token",
        "ASSAY_API_URL": "http://assay.com",
        "ASSAY_API_TOKEN": "assay-token",
        "FOUNDRY_API_URL": "http://foundry.com",
        "FOUNDRY_API_TOKEN": "foundry-token",
        # GITLAB_PROJECT_ID missing
    }

    with patch.dict(os.environ, env_vars, clear=True):
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            with patch("coreason_publisher.main.GitLocal"):
                with patch("coreason_publisher.main.GitLFS"):
                    orch = get_orchestrator()
                    # Should fallback to "0"
                    assert isinstance(orch.git_provider, GitLabProvider)
                    assert orch.git_provider.project_id == "0"


def test_get_orchestrator_failure() -> None:
    """Test initialization failure (missing env var)."""
    # Missing variables should cause ValueError in client inits
    with patch.dict(os.environ, {}, clear=True):
        with patch("pathlib.Path.cwd", return_value=Path("/tmp")):
            with pytest.raises(Exit) as e:
                get_orchestrator()
            assert e.value.exit_code == 1


def test_main_entry_point() -> None:
    """Test the main entry point function."""
    with patch("coreason_publisher.main.app") as mock_app:
        main()
        mock_app.assert_called_once()

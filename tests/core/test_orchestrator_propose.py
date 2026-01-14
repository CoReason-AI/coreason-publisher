# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_publisher

import json
from pathlib import Path
from typing import Any
from unittest.mock import ANY, MagicMock

import pytest

from coreason_publisher.core.artifact_bundler import ArtifactBundler
from coreason_publisher.core.assay_client import AssayClient
from coreason_publisher.core.electronic_signer import ElectronicSigner
from coreason_publisher.core.foundry_client import FoundryClient
from coreason_publisher.core.git_lfs import GitLFS
from coreason_publisher.core.git_local import GitLocal
from coreason_publisher.core.git_provider import GitProvider
from coreason_publisher.core.orchestrator import PublisherOrchestrator
from coreason_publisher.core.version_manager import BumpType, VersionManager


@pytest.fixture  # type: ignore[misc]
def mock_dependencies() -> dict[str, MagicMock]:
    return {
        "assay_client": MagicMock(spec=AssayClient),
        "foundry_client": MagicMock(spec=FoundryClient),
        "git_provider": MagicMock(spec=GitProvider),
        "git_local": MagicMock(spec=GitLocal),
        "git_lfs": MagicMock(spec=GitLFS),
        "artifact_bundler": MagicMock(spec=ArtifactBundler),
        "electronic_signer": MagicMock(spec=ElectronicSigner),
        "version_manager": MagicMock(spec=VersionManager),
    }


def test_propose_release_success(tmp_path: Path, mock_dependencies: dict[str, Any]) -> None:
    """Test the happy path for propose_release."""
    deps = mock_dependencies

    # Setup
    workspace_path = tmp_path
    orchestrator = PublisherOrchestrator(workspace_path, **deps)

    # Mocks return values
    deps["assay_client"].get_latest_report.return_value = {"council": {}, "results": {"pass": True}}
    deps["version_manager"].get_current_version.return_value = "v1.0.0"
    deps["version_manager"].calculate_next_version.return_value = "v1.1.0"
    deps["electronic_signer"].create_signature.return_value = "dummy-hash"
    deps["electronic_signer"].format_commit_message.return_value = "Commit Message"
    deps["git_provider"].create_merge_request.return_value = 123

    # Execute
    orchestrator.propose_release(
        project_id="proj-1",
        foundry_draft_id="draft-1",
        bump_type=BumpType.MINOR,
        sre_user_id="user-1",
        release_description="Test release",
    )

    # Verify Assay Report Saved
    evidence_file = workspace_path / "evidence" / "assay_report.json"
    assert evidence_file.exists()
    with open(evidence_file) as f:
        data = json.load(f)
        assert data["results"]["pass"] is True

    # Verify Interactions
    deps["assay_client"].get_latest_report.assert_called_once_with("proj-1")
    deps["version_manager"].calculate_next_version.assert_called_once_with("v1.0.0", BumpType.MINOR)
    deps["git_local"].checkout_new_branch.assert_called_once_with("candidate/v1.1.0")
    deps["version_manager"].update_files.assert_called_once_with(workspace_path, "v1.1.0")
    deps["artifact_bundler"].bundle.assert_called_once_with(workspace_path)
    deps["electronic_signer"].create_signature.assert_called_once_with(workspace_path, "user-1")
    deps["git_local"].add_all.assert_called_once()
    deps["git_local"].commit.assert_called_once_with("Commit Message")
    deps["electronic_signer"].send_audit_to_veritas.assert_called_once_with("user-1", "dummy-hash", "SRE")
    # Verify strict LFS check before push
    deps["git_lfs"].verify_ready.assert_called_once_with(workspace_path)
    deps["git_local"].push.assert_called_once_with("candidate/v1.1.0")
    deps["git_provider"].create_merge_request.assert_called_once_with(
        source_branch="candidate/v1.1.0", target_branch="main", title="Release v1.1.0", description=ANY
    )
    deps["foundry_client"].submit_for_review.assert_called_once_with("draft-1", type="release")
    deps["git_provider"].post_comment.assert_called_once()


def test_propose_release_mr_failure(tmp_path: Path, mock_dependencies: dict[str, Any]) -> None:
    """Test that Foundry submission is skipped if MR creation fails."""
    deps = mock_dependencies
    workspace_path = tmp_path
    orchestrator = PublisherOrchestrator(workspace_path, **deps)

    # Setup basic returns
    deps["assay_client"].get_latest_report.return_value = {"data": "ok"}
    deps["version_manager"].calculate_next_version.return_value = "v1.1.0"

    # Simulate MR failure
    deps["git_provider"].create_merge_request.side_effect = RuntimeError("GitLab Error")

    with pytest.raises(RuntimeError, match="GitLab Error"):
        orchestrator.propose_release(
            project_id="p", foundry_draft_id="d", bump_type=BumpType.PATCH, sre_user_id="u", release_description="desc"
        )

    # Verify Foundry Client was NOT called
    deps["foundry_client"].submit_for_review.assert_not_called()


def test_propose_release_lfs_verification_fails(tmp_path: Path, mock_dependencies: dict[str, Any]) -> None:
    """
    Test Edge Case: LFS Verification fails (e.g., hooks missing).
    The system MUST strictly block the push operation.
    """
    deps = mock_dependencies
    workspace_path = tmp_path
    orchestrator = PublisherOrchestrator(workspace_path, **deps)

    # Setup basic returns
    deps["assay_client"].get_latest_report.return_value = {"data": "ok"}
    deps["version_manager"].calculate_next_version.return_value = "v1.1.0"
    deps["electronic_signer"].create_signature.return_value = "sig"

    # Simulate LFS verification failure
    deps["git_lfs"].verify_ready.side_effect = RuntimeError("LFS hooks missing")

    # Execute
    with pytest.raises(RuntimeError, match="LFS hooks missing"):
        orchestrator.propose_release(
            project_id="p", foundry_draft_id="d", bump_type=BumpType.PATCH, sre_user_id="u", release_description="desc"
        )

    # CRITICAL ASSERTION: Push must NOT be called
    deps["git_local"].push.assert_not_called()

    # Foundry submission must also be skipped
    deps["foundry_client"].submit_for_review.assert_not_called()
    deps["git_provider"].create_merge_request.assert_not_called()

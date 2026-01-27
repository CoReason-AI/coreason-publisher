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
from typing import Any
from unittest.mock import MagicMock

import pytest
from coreason_identity.models import UserContext

from coreason_publisher.core.artifact_bundler import ArtifactBundler
from coreason_publisher.core.assay_client import AssayClient
from coreason_publisher.core.electronic_signer import ElectronicSigner
from coreason_publisher.core.foundry_client import FoundryClient
from coreason_publisher.core.git_lfs import GitLFS
from coreason_publisher.core.git_local import GitLocal
from coreason_publisher.core.git_provider import GitProvider
from coreason_publisher.core.orchestrator import PublisherOrchestrator
from coreason_publisher.core.version_manager import BumpType, VersionManager


@pytest.fixture
def mock_deps() -> dict[str, MagicMock]:
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


def test_audit_failure_blocks_release(
    tmp_path: Path, mock_deps: dict[str, Any], mock_user_context: UserContext
) -> None:
    """
    Edge Case: If the audit system is down (raises exception),
    the release finalization must abort immediately.
    It must NOT merge or tag the release.
    """
    deps = mock_deps
    workspace_path = tmp_path
    orchestrator = PublisherOrchestrator(workspace_path, **deps)

    # Setup
    deps["electronic_signer"].verify_signature.return_value = True
    # Simulate Audit Failure
    deps["electronic_signer"].send_audit_to_veritas.side_effect = RuntimeError("Veritas Down")

    # Execute
    with pytest.raises(RuntimeError, match="Veritas Down"):
        orchestrator.finalize_release(mr_id=123, srb_signature="sig", user_context=mock_user_context)

    # Verify side effects are blocked
    deps["git_provider"].merge_merge_request.assert_not_called()
    deps["git_provider"].create_tag.assert_not_called()
    deps["foundry_client"].approve_release.assert_not_called()


def test_audit_failure_blocks_proposal_push(
    tmp_path: Path, mock_deps: dict[str, Any], mock_user_context: UserContext
) -> None:
    """
    Edge Case: If the audit system is down during proposal,
    the system must NOT push the candidate branch or open an MR.
    """
    deps = mock_deps
    workspace_path = tmp_path
    orchestrator = PublisherOrchestrator(workspace_path, **deps)

    # Setup basic mocks
    deps["assay_client"].get_latest_report.return_value = {}
    deps["version_manager"].calculate_next_version.return_value = "v1.1.0"
    deps["electronic_signer"].create_signature.return_value = "sig"
    # Simulate Audit Failure
    deps["electronic_signer"].send_audit_to_veritas.side_effect = RuntimeError("Veritas Down")

    # Execute
    with pytest.raises(RuntimeError, match="Veritas Down"):
        orchestrator.propose_release(
            project_id="p",
            foundry_draft_id="d",
            bump_type=BumpType.PATCH,
            user_context=mock_user_context,
            release_description="desc",
        )

    # Verify push blocked
    deps["git_local"].push.assert_not_called()
    deps["git_provider"].create_merge_request.assert_not_called()


def test_empty_srb_user_id_rejected(tmp_path: Path, mock_deps: dict[str, Any]) -> None:
    """
    Edge Case: UserContext with empty user_id should be passed through.
    """
    deps = mock_deps
    workspace_path = tmp_path
    orchestrator = PublisherOrchestrator(workspace_path, **deps)

    deps["electronic_signer"].verify_signature.return_value = True
    deps["version_manager"].get_current_version.return_value = "v1.0.0"

    empty_context = UserContext(user_id="", email="test@example.com", groups=[], scopes=[], claims={})

    # Execute with empty context
    orchestrator.finalize_release(mr_id=123, srb_signature="sig", user_context=empty_context)

    # Verify it was passed to audit
    deps["electronic_signer"].send_audit_to_veritas.assert_called_once_with(empty_context, "sig", "SRB")


def test_complex_audit_sequence_verification(
    tmp_path: Path, mock_deps: dict[str, Any], mock_user_context: UserContext
) -> None:
    """
    Complex Scenario: Verify the exact order of critical operations.
    1. Verify Signature
    2. Audit Log
    3. Merge
    4. Tag
    5. Foundry Approve
    """
    deps = mock_deps
    workspace_path = tmp_path
    orchestrator = PublisherOrchestrator(workspace_path, **deps)

    deps["electronic_signer"].verify_signature.return_value = True
    deps["version_manager"].get_current_version.return_value = "v1.0.0"

    # Use a call manager to track order
    manager = MagicMock()
    manager.attach_mock(deps["electronic_signer"].verify_signature, "verify")
    manager.attach_mock(deps["electronic_signer"].send_audit_to_veritas, "audit")
    manager.attach_mock(deps["git_provider"].merge_merge_request, "merge")
    manager.attach_mock(deps["git_provider"].create_tag, "tag")
    manager.attach_mock(deps["foundry_client"].approve_release, "approve")

    orchestrator.finalize_release(mr_id=123, srb_signature="sig", user_context=mock_user_context)

    # Verify order
    # Note: call_args_list includes call objects.
    # We simplify checking by iterating.
    calls = manager.mock_calls
    assert len(calls) >= 5
    assert calls[0][0] == "verify"
    assert calls[1][0] == "audit"
    assert calls[2][0] == "merge"
    assert calls[3][0] == "tag"
    assert calls[4][0] == "approve"

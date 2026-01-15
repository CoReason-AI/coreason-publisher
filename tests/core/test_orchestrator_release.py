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

from coreason_publisher.core.artifact_bundler import ArtifactBundler
from coreason_publisher.core.assay_client import AssayClient
from coreason_publisher.core.electronic_signer import ElectronicSigner
from coreason_publisher.core.foundry_client import FoundryClient
from coreason_publisher.core.git_lfs import GitLFS
from coreason_publisher.core.git_local import GitLocal
from coreason_publisher.core.git_provider import GitProvider
from coreason_publisher.core.orchestrator import PublisherOrchestrator
from coreason_publisher.core.version_manager import VersionManager


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


def test_finalize_release_success(tmp_path: Path, mock_dependencies: dict[str, Any]) -> None:
    """Test the happy path for finalize_release."""
    deps = mock_dependencies
    workspace_path = tmp_path
    orchestrator = PublisherOrchestrator(workspace_path, **deps)

    # Setup
    mr_id = 123
    signature = "valid-signature"
    srb_user_id = "srb-user"

    deps["electronic_signer"].verify_signature.return_value = True
    deps["version_manager"].get_current_version.return_value = "v1.2.0"

    # Execute
    orchestrator.finalize_release(mr_id, signature, srb_user_id)

    # Verify
    deps["electronic_signer"].verify_signature.assert_called_once_with(workspace_path, signature)
    deps["electronic_signer"].send_audit_to_veritas.assert_called_once_with(srb_user_id, signature, "SRB")
    deps["git_provider"].merge_merge_request.assert_called_once_with(mr_id)
    deps["git_provider"].create_tag.assert_called_once_with(tag_name="v1.2.0", ref="main", message="Release v1.2.0")
    deps["foundry_client"].approve_release.assert_called_once_with(mr_id, signature)


def test_finalize_release_invalid_signature(tmp_path: Path, mock_dependencies: dict[str, Any]) -> None:
    """Test that release aborts if signature is invalid."""
    deps = mock_dependencies
    workspace_path = tmp_path
    orchestrator = PublisherOrchestrator(workspace_path, **deps)

    deps["electronic_signer"].verify_signature.return_value = False

    with pytest.raises(ValueError, match="Signature verification failed"):
        orchestrator.finalize_release(123, "bad-sig", "srb-user")

    deps["electronic_signer"].send_audit_to_veritas.assert_not_called()
    deps["git_provider"].merge_merge_request.assert_not_called()
    deps["foundry_client"].approve_release.assert_not_called()


def test_finalize_release_no_version(tmp_path: Path, mock_dependencies: dict[str, Any]) -> None:
    """Test failure when version cannot be determined."""
    deps = mock_dependencies
    workspace_path = tmp_path
    orchestrator = PublisherOrchestrator(workspace_path, **deps)

    deps["electronic_signer"].verify_signature.return_value = True
    deps["version_manager"].get_current_version.return_value = None

    with pytest.raises(RuntimeError, match="Could not determine version"):
        orchestrator.finalize_release(123, "sig", "srb-user")

    deps["git_provider"].merge_merge_request.assert_not_called()

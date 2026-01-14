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

# We mock other dependencies
from coreason_publisher.core.assay_client import AssayClient
from coreason_publisher.core.electronic_signer import ElectronicSigner
from coreason_publisher.core.foundry_client import FoundryClient
from coreason_publisher.core.git_lfs import GitLFS
from coreason_publisher.core.git_local import GitLocal
from coreason_publisher.core.git_provider import GitProvider
from coreason_publisher.core.orchestrator import PublisherOrchestrator
from coreason_publisher.core.version_manager import VersionManager


@pytest.fixture  # type: ignore[misc]
def mock_deps_with_real_signer() -> dict[str, Any]:
    return {
        "assay_client": MagicMock(spec=AssayClient),
        "foundry_client": MagicMock(spec=FoundryClient),
        "git_provider": MagicMock(spec=GitProvider),
        "git_local": MagicMock(spec=GitLocal),
        "git_lfs": MagicMock(spec=GitLFS),
        "artifact_bundler": MagicMock(spec=ArtifactBundler),
        "electronic_signer": ElectronicSigner(),  # Real implementation
        "version_manager": MagicMock(spec=VersionManager),
    }


def test_release_tampered_bundle_integration(tmp_path: Path, mock_deps_with_real_signer: dict[str, Any]) -> None:
    """
    Integration test:
    1. Bundle is signed (hash calculated).
    2. File is modified on disk (tampering).
    3. Finalize release is called.
    4. Should fail due to signature mismatch.
    """
    deps = mock_deps_with_real_signer
    workspace_path = tmp_path

    # Create some files
    (workspace_path / "data.txt").write_text("Original content")

    orchestrator = PublisherOrchestrator(workspace_path, **deps)

    # 1. Sign (Simulate SRE signing in Propose phase)
    # We manually call create_signature to get the valid signature
    signer: ElectronicSigner = deps["electronic_signer"]
    valid_signature = signer.create_signature(workspace_path, "sre-user")

    # Setup mocks for release
    deps["version_manager"].get_current_version.return_value = "v1.0.0"

    # 2. Tamper with file
    (workspace_path / "data.txt").write_text("Tampered content")

    # 3. Finalize Release
    with pytest.raises(ValueError, match="Signature verification failed"):
        orchestrator.finalize_release(mr_id=123, srb_signature=valid_signature, srb_user_id="srb-user")

    # Verify no merge happened
    deps["git_provider"].merge_merge_request.assert_not_called()


def test_release_valid_bundle_integration(tmp_path: Path, mock_deps_with_real_signer: dict[str, Any]) -> None:
    """
    Integration test:
    1. Bundle is signed.
    2. No changes.
    3. Finalize release is called.
    4. Should succeed.
    """
    deps = mock_deps_with_real_signer
    workspace_path = tmp_path

    (workspace_path / "data.txt").write_text("Original content")

    orchestrator = PublisherOrchestrator(workspace_path, **deps)
    signer: ElectronicSigner = deps["electronic_signer"]
    valid_signature = signer.create_signature(workspace_path, "sre-user")

    deps["version_manager"].get_current_version.return_value = "v1.0.0"

    orchestrator.finalize_release(mr_id=123, srb_signature=valid_signature, srb_user_id="srb-user")

    deps["git_provider"].merge_merge_request.assert_called_once_with(123)

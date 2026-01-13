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
from unittest.mock import MagicMock

import pytest

from coreason_publisher.core.artifact_bundler import ArtifactBundler
from coreason_publisher.core.assay_client import AssayClient
from coreason_publisher.core.electronic_signer import ElectronicSigner
from coreason_publisher.core.foundry_client import FoundryClient
from coreason_publisher.core.git_local import GitLocal
from coreason_publisher.core.git_provider import GitProvider
from coreason_publisher.core.orchestrator import PublisherOrchestrator
from coreason_publisher.core.version_manager import VersionManager


@pytest.fixture  # type: ignore[misc]
def mock_clients() -> dict[str, MagicMock]:
    return {
        "assay_client": MagicMock(spec=AssayClient),
        "foundry_client": MagicMock(spec=FoundryClient),
        "git_provider": MagicMock(spec=GitProvider),
        "git_local": MagicMock(spec=GitLocal),
        "artifact_bundler": MagicMock(spec=ArtifactBundler),
        "electronic_signer": MagicMock(spec=ElectronicSigner),
        "version_manager": MagicMock(spec=VersionManager),
    }


def test_reject_release(mock_clients: dict[str, MagicMock], tmp_path: Path) -> None:
    orchestrator = PublisherOrchestrator(
        workspace_path=tmp_path,
        **mock_clients,
    )

    mr_id = 123
    draft_id = "draft-456"
    reason = "Test failures in assay report"

    orchestrator.reject_release(mr_id, draft_id, reason)

    # Verify Git Provider interaction
    mock_clients["git_provider"].post_comment.assert_called_once_with(mr_id, f"Changes Requested: {reason}")

    # Verify Foundry Client interaction
    mock_clients["foundry_client"].reject_release.assert_called_once_with(draft_id, reason)

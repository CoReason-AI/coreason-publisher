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
from unittest.mock import MagicMock, patch

import pytest

from coreason_publisher.config import PublisherConfig
from coreason_publisher.core.artifact_bundler import ArtifactBundler
from coreason_publisher.core.certificate_generator import CertificateGenerator
from coreason_publisher.core.council_snapshot import CouncilSnapshot
from coreason_publisher.core.git_lfs import GitLFS
from coreason_publisher.core.remote_storage import MockStorageProvider


@pytest.fixture  # type: ignore[misc]
def mock_config() -> PublisherConfig:
    return PublisherConfig(lfs_threshold_mb=100, remote_storage_threshold_mb=70 * 1024)


@pytest.fixture  # type: ignore[misc]
def mock_git_lfs() -> MagicMock:
    lfs = MagicMock(spec=GitLFS)
    lfs.is_installed.return_value = True
    lfs.is_initialized.return_value = True
    lfs.find_large_files.return_value = []
    return lfs


@pytest.fixture  # type: ignore[misc]
def mock_council_snapshot() -> MagicMock:
    return MagicMock(spec=CouncilSnapshot)


@pytest.fixture  # type: ignore[misc]
def mock_storage_provider() -> MagicMock:
    return MagicMock(spec=MockStorageProvider)


@pytest.fixture  # type: ignore[misc]
def mock_certificate_generator() -> MagicMock:
    mock = MagicMock(spec=CertificateGenerator)
    mock.generate.return_value = "MOCKED CERTIFICATE"
    return mock


@pytest.fixture  # type: ignore[misc]
def artifact_bundler(
    mock_config: PublisherConfig,
    mock_git_lfs: MagicMock,
    mock_council_snapshot: MagicMock,
    mock_storage_provider: MagicMock,
    mock_certificate_generator: MagicMock,
) -> ArtifactBundler:
    return ArtifactBundler(
        mock_config, mock_git_lfs, mock_council_snapshot, mock_storage_provider, mock_certificate_generator
    )


def test_move_model_artifacts_symlinks(artifact_bundler: ArtifactBundler, tmp_path: Path) -> None:
    """Test that symlinks to model files are ignored and not moved."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Create a real model file
    real_model = workspace / "real_model.bin"
    real_model.write_text("content")

    # Create a symlink to it
    link_model = workspace / "link_model.bin"
    link_model.symlink_to(real_model)

    artifact_bundler._move_model_artifacts(workspace)

    distilled = workspace / "models" / "distilled"

    # Real model should be moved
    assert (distilled / "real_model.bin").exists()

    # Symlink should NOT be moved.
    # The symlink remains in workspace, but might be broken because target moved.
    # Check it is still a symlink.
    assert link_model.is_symlink()
    assert not (distilled / "link_model.bin").exists()


def test_move_model_artifacts_name_collision(artifact_bundler: ArtifactBundler, tmp_path: Path) -> None:
    """Test behavior when multiple files have same name."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    (workspace / "subdir1").mkdir()
    (workspace / "subdir2").mkdir()

    file1 = workspace / "subdir1" / "model.bin"
    file1.write_text("content1")

    file2 = workspace / "subdir2" / "model.bin"
    file2.write_text("content2")

    # We can't guarantee order of rglob, so we just verify one wins
    artifact_bundler._move_model_artifacts(workspace)

    distilled = workspace / "models" / "distilled"
    dest = distilled / "model.bin"

    assert dest.exists()
    content = dest.read_text()
    assert content in ["content1", "content2"]

    # Verify both source files are gone (moved)
    assert not file1.exists()
    assert not file2.exists()


def test_complex_scenario(
    artifact_bundler: ArtifactBundler,
    mock_git_lfs: MagicMock,
    mock_storage_provider: MagicMock,
    tmp_path: Path,
) -> None:
    """
    Test a complex scenario with:
    - Ultra-large file (>70GB) -> Remote Storage
    - Large file (>100MB) -> LFS
    - Small model file -> Moved
    - Ignored file -> Untouched
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # 1. Ultra-large file
    ultra_large = workspace / "ultra_large.bin"
    ultra_large.write_text("dummy")
    mock_storage_provider.upload.return_value = "remote-hash"

    # 2. Large file (LFS)
    # Note: .pt is in MODEL_EXTENSIONS, so it will be moved too!
    lfs_file = workspace / "large_file.pt"
    lfs_file.write_text("dummy")
    mock_git_lfs.find_large_files.return_value = ["large_file.pt"]

    # 3. Small model to move
    small_model = workspace / "small.safetensors"
    small_model.write_text("weights")

    # 4. Ignored file
    ignored = workspace / "README.md"
    ignored.touch()

    # Patch stat for ultra-large file
    original_stat = Path.stat
    target_path_str = str(ultra_large.absolute())

    def side_effect(self: Path, *args: Any, **kwargs: Any) -> object:
        try:
            if str(self.absolute()) == target_path_str:
                m = MagicMock()
                m.st_size = 70 * 1024 * 1024 * 1024 + 1
                m.st_mode = original_stat(self).st_mode
                return m
        except Exception:
            pass
        return original_stat(self, *args, **kwargs)

    with patch("pathlib.Path.stat", side_effect=side_effect, autospec=True):
        # We need to manually call bundle components or just run bundle() if we mock council snapshot
        # Let's run bundle() but we need evidence folder for snapshot
        (workspace / "evidence").mkdir()
        (workspace / "evidence" / "assay_report.json").write_text("{}")

        mock_git_lfs.is_initialized.return_value = False

        artifact_bundler.bundle(workspace)

    # Verify Ultra-Large
    mock_storage_provider.upload.assert_called_with(ultra_large)
    # It should have been moved to distilled because it ends in .bin
    distilled_ultra = workspace / "models" / "distilled" / "ultra_large.bin"
    assert distilled_ultra.exists()
    assert distilled_ultra.read_text() == "pointer:remote-hash\n"
    assert not ultra_large.exists()

    # Verify LFS
    mock_git_lfs.initialize.assert_called_with(workspace)
    mock_git_lfs.track_patterns.assert_called_with(workspace, ["large_file.pt"])

    # Verify Move (Small & LFS file if moved)
    distilled = workspace / "models" / "distilled"
    assert (distilled / "small.safetensors").exists()
    assert not small_model.exists()

    # Check if large_file.pt was moved (it is .pt so yes)
    assert (distilled / "large_file.pt").exists()

    # Verify Ignored
    assert ignored.exists()


def test_upload_failure(artifact_bundler: ArtifactBundler, mock_storage_provider: MagicMock, tmp_path: Path) -> None:
    """Test that upload failure propagates."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    large_file = workspace / "huge.bin"
    large_file.touch()

    mock_storage_provider.upload.side_effect = RuntimeError("Upload failed")

    # Patch stat
    original_stat = Path.stat
    target_path_str = str(large_file.absolute())

    def side_effect(self: Path, *args: Any, **kwargs: Any) -> object:
        if str(self.absolute()) == target_path_str:
            m = MagicMock()
            m.st_size = 70 * 1024 * 1024 * 1024 + 1
            m.st_mode = original_stat(self).st_mode
            return m
        return original_stat(self, *args, **kwargs)

    with patch("pathlib.Path.stat", side_effect=side_effect, autospec=True):
        with pytest.raises(RuntimeError, match="Upload failed"):
            artifact_bundler._handle_remote_storage(workspace)

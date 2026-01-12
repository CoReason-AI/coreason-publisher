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

from coreason_publisher.core.artifact_bundler import ArtifactBundler
from coreason_publisher.core.certificate_generator import CertificateGenerator
from coreason_publisher.core.council_snapshot import CouncilSnapshot
from coreason_publisher.core.git_lfs import GitLFS
from coreason_publisher.core.remote_storage import MockStorageProvider


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
    mock.generate.return_value = "# Certificate of Analysis\n\nPASSED"
    return mock


@pytest.fixture  # type: ignore[misc]
def artifact_bundler(
    mock_git_lfs: MagicMock,
    mock_council_snapshot: MagicMock,
    mock_storage_provider: MagicMock,
    mock_certificate_generator: MagicMock,
) -> ArtifactBundler:
    return ArtifactBundler(mock_git_lfs, mock_council_snapshot, mock_storage_provider, mock_certificate_generator)


def test_move_model_artifacts(artifact_bundler: ArtifactBundler, tmp_path: Path) -> None:
    """Test that allow-listed model artifacts are moved to models/distilled/."""
    # Setup workspace
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Create source files
    (workspace / "adapter_config.json").touch()
    (workspace / "model.safetensors").touch()
    (workspace / "weights.bin").touch()
    (workspace / "model.pt").touch()

    # Create ignored files
    (workspace / "README.md").touch()
    (workspace / "other.json").touch()

    # Create ignored directories
    (workspace / "models").mkdir()
    (workspace / "models" / "existing.bin").touch()

    (workspace / "tests").mkdir()
    (workspace / "tests" / "test_model.bin").touch()

    (workspace / ".git").mkdir()
    (workspace / ".git" / "config").touch()

    # Run bundler method directly
    artifact_bundler._move_model_artifacts(workspace)

    distilled = workspace / "models" / "distilled"

    # Verify moves
    assert (distilled / "adapter_config.json").exists()
    assert (distilled / "model.safetensors").exists()
    assert (distilled / "weights.bin").exists()
    assert (distilled / "model.pt").exists()

    assert not (workspace / "adapter_config.json").exists()
    assert not (workspace / "model.safetensors").exists()

    # Verify ignored
    assert (workspace / "README.md").exists()
    assert (workspace / "other.json").exists()
    assert (workspace / "models" / "existing.bin").exists()
    assert (workspace / "tests" / "test_model.bin").exists()
    assert (workspace / ".git" / "config").exists()


def test_move_model_artifacts_overwrite(artifact_bundler: ArtifactBundler, tmp_path: Path) -> None:
    """Test overwriting existing files in distilled directory."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    distilled = workspace / "models" / "distilled"
    distilled.mkdir(parents=True)

    # Create existing file
    (distilled / "model.bin").write_text("old content")

    # Create new file
    (workspace / "model.bin").write_text("new content")

    artifact_bundler._move_model_artifacts(workspace)

    assert (distilled / "model.bin").read_text() == "new content"
    assert not (workspace / "model.bin").exists()


def test_handle_remote_storage(
    artifact_bundler: ArtifactBundler, mock_storage_provider: MagicMock, tmp_path: Path
) -> None:
    """Test that files > 70GB are replaced by pointers."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    large_file = workspace / "huge_model.bin"
    large_file.write_text("dummy content")

    # Create a small file that shouldn't be touched
    small_file = workspace / "small_model.bin"
    small_file.write_text("small content")

    # Create .git to test exclusion in handle_remote_storage
    (workspace / ".git").mkdir()
    (workspace / ".git" / "big_object").write_text("should be ignored")

    # Mock upload
    mock_storage_provider.upload.return_value = "hash-123"

    # Patch pathlib.Path.stat to return a large size for our specific file
    original_stat = Path.stat

    # Use string comparison to avoid recursion in resolve()
    target_path_str = str(large_file.absolute())

    def side_effect(self: Path, *args: Any, **kwargs: Any) -> object:
        try:
            # Avoid resolve(), use absolute() which is just string manipulation mostly
            if str(self.absolute()) == target_path_str:
                real_stat = original_stat(self, *args, **kwargs)
                m = MagicMock()
                m.st_size = 70 * 1024 * 1024 * 1024 + 1
                m.st_mode = real_stat.st_mode
                return m
        except Exception:
            pass
        return original_stat(self, *args, **kwargs)

    with patch("pathlib.Path.stat", side_effect=side_effect, autospec=True):
        artifact_bundler._handle_remote_storage(workspace)

    mock_storage_provider.upload.assert_called_once_with(large_file)

    # Verify content replaced
    content = large_file.read_text()
    assert content == "pointer:hash-123\n"

    # Verify small file untouched
    assert small_file.read_text() == "small content"
    # Verify .git untouched
    assert (workspace / ".git" / "big_object").read_text() == "should be ignored"


def test_handle_remote_storage_oserror(
    artifact_bundler: ArtifactBundler, mock_storage_provider: MagicMock, tmp_path: Path
) -> None:
    """Test handling of OSError during file size check."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    f = workspace / "file.bin"
    f.touch()

    original_stat = Path.stat

    def side_effect(self: Path, *args: Any, **kwargs: Any) -> object:
        if self.name == "file.bin":
            raise OSError("access denied")
        return original_stat(self, *args, **kwargs)

    with patch("pathlib.Path.stat", side_effect=side_effect, autospec=True):
        # Should not raise exception
        artifact_bundler._handle_remote_storage(workspace)

    mock_storage_provider.upload.assert_not_called()


def test_configure_lfs(artifact_bundler: ArtifactBundler, mock_git_lfs: MagicMock, tmp_path: Path) -> None:
    """Test LFS configuration."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Mock LFS finding files
    large_files = ["models/distilled/model.bin"]
    mock_git_lfs.find_large_files.return_value = large_files

    # Ensure initialize is called
    mock_git_lfs.is_initialized.return_value = False

    artifact_bundler._configure_lfs(workspace)

    mock_git_lfs.initialize.assert_called_once_with(workspace)
    mock_git_lfs.track_patterns.assert_called_once_with(workspace, large_files)


def test_configure_lfs_already_initialized(
    artifact_bundler: ArtifactBundler, mock_git_lfs: MagicMock, tmp_path: Path
) -> None:
    """Test LFS configuration when already initialized."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    mock_git_lfs.find_large_files.return_value = []
    mock_git_lfs.is_initialized.return_value = True

    artifact_bundler._configure_lfs(workspace)

    mock_git_lfs.initialize.assert_not_called()
    mock_git_lfs.track_patterns.assert_not_called()


def test_configure_lfs_not_installed(
    artifact_bundler: ArtifactBundler, mock_git_lfs: MagicMock, tmp_path: Path
) -> None:
    """Test error when LFS not installed."""
    workspace = tmp_path / "workspace"

    mock_git_lfs.is_installed.return_value = False

    with pytest.raises(RuntimeError, match="Git LFS is not installed"):
        artifact_bundler._configure_lfs(workspace)


def test_bundle_flow(
    artifact_bundler: ArtifactBundler,
    mock_git_lfs: MagicMock,
    mock_council_snapshot: MagicMock,
    mock_certificate_generator: MagicMock,
    tmp_path: Path,
) -> None:
    """Test the full bundle flow."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "evidence").mkdir()
    (workspace / "evidence" / "assay_report.json").write_text("{}")

    mock_git_lfs.is_initialized.return_value = True

    # Just ensure no errors are raised and calls are made
    artifact_bundler.bundle(workspace)

    # initialize shouldn't be called if is_initialized is True
    mock_git_lfs.initialize.assert_not_called()
    mock_git_lfs.find_large_files.assert_called()
    mock_council_snapshot.create_snapshot.assert_called()
    mock_certificate_generator.generate.assert_called_once()
    assert (workspace / "CERTIFICATE.md").exists()
    assert (workspace / "CERTIFICATE.md").read_text() == "# Certificate of Analysis\n\nPASSED"


def test_bundle_flow_missing_workspace(artifact_bundler: ArtifactBundler, tmp_path: Path) -> None:
    """Test error when workspace missing."""
    workspace = tmp_path / "missing"
    with pytest.raises(FileNotFoundError):
        artifact_bundler.bundle(workspace)


def test_bundle_certificate_generation_error(
    artifact_bundler: ArtifactBundler,
    mock_certificate_generator: MagicMock,
    tmp_path: Path,
) -> None:
    """Test that runtime error is raised if certificate generation fails."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "evidence").mkdir()
    (workspace / "evidence" / "assay_report.json").write_text("{}")

    mock_certificate_generator.generate.side_effect = RuntimeError("Generation failed")

    with pytest.raises(RuntimeError, match="Failed to generate CERTIFICATE.md"):
        artifact_bundler.bundle(workspace)


def test_bundle_certificate_write_error(
    artifact_bundler: ArtifactBundler,
    mock_certificate_generator: MagicMock,
    tmp_path: Path,
) -> None:
    """Test that runtime error is raised if certificate write fails."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "evidence").mkdir()
    (workspace / "evidence" / "assay_report.json").write_text("{}")

    mock_certificate_generator.generate.return_value = "content"

    # Patch open to fail when writing CERTIFICATE.md
    # We need to wrap existing open so reading assay_report.json works
    original_open = open

    def side_effect(file: Any, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        if "CERTIFICATE.md" in str(file) and "w" in mode:
            raise OSError("Write access denied")
        return original_open(file, mode, *args, **kwargs)

    with patch("builtins.open", side_effect=side_effect):
        with pytest.raises(RuntimeError, match="Failed to generate CERTIFICATE.md"):
            artifact_bundler.bundle(workspace)


def test_bundle_passes_correct_data_to_generator(
    artifact_bundler: ArtifactBundler,
    mock_certificate_generator: MagicMock,
    tmp_path: Path,
) -> None:
    """Test that the exact data from assay_report.json is passed to the generator."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "evidence").mkdir()

    import json

    report_data = {"council": {"proposer": "me"}, "results": {"pass": True}}

    (workspace / "evidence" / "assay_report.json").write_text(json.dumps(report_data))

    artifact_bundler.bundle(workspace)

    mock_certificate_generator.generate.assert_called_once_with(report_data)

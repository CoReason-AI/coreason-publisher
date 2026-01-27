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


@pytest.fixture
def mock_config() -> PublisherConfig:
    return PublisherConfig(lfs_threshold_mb=100, remote_storage_threshold_mb=70 * 1024)


@pytest.fixture
def mock_git_lfs() -> MagicMock:
    lfs = MagicMock(spec=GitLFS)
    lfs.is_installed.return_value = True
    lfs.is_initialized.return_value = True
    lfs.find_large_files.return_value = []
    return lfs


@pytest.fixture
def mock_council_snapshot() -> MagicMock:
    return MagicMock(spec=CouncilSnapshot)


@pytest.fixture
def mock_storage_provider() -> MagicMock:
    return MagicMock(spec=MockStorageProvider)


@pytest.fixture
def mock_certificate_generator() -> MagicMock:
    mock = MagicMock(spec=CertificateGenerator)
    mock.generate.return_value = "MOCKED CERTIFICATE"
    return mock


@pytest.fixture
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


def test_remote_storage_boundary_conditions(
    artifact_bundler: ArtifactBundler, mock_storage_provider: MagicMock, mock_config: PublisherConfig, tmp_path: Path
) -> None:
    """
    Test boundary conditions for remote storage threshold.
    Files equal to threshold -> No upload.
    Files > threshold -> Upload.
    """
    mock_config.remote_storage_threshold_mb = 1  # 1 MB = 1048576 bytes
    threshold = 1048576

    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Create file exact size
    exact_file = workspace / "exact.bin"
    with open(exact_file, "wb") as f:
        f.write(b"\0" * threshold)

    # Create file just over size
    over_file = workspace / "over.bin"
    with open(over_file, "wb") as f:
        f.write(b"\0" * (threshold + 1))

    mock_storage_provider.upload.return_value = "hash"

    artifact_bundler._handle_remote_storage(workspace)

    # Verify upload called for over_file but not exact_file
    mock_storage_provider.upload.assert_called_once_with(over_file)
    assert not exact_file.read_text().startswith("pointer:")
    assert over_file.read_text().startswith("pointer:")


def test_inverted_thresholds(
    artifact_bundler: ArtifactBundler,
    mock_storage_provider: MagicMock,
    mock_git_lfs: MagicMock,
    mock_config: PublisherConfig,
    tmp_path: Path,
) -> None:
    """
    Test scenario where Remote Storage Threshold < LFS Threshold.
    Files in between should be uploaded to Remote Storage and the pointer should NOT be tracked by LFS
    (since pointer is small).
    """
    # LFS = 100MB, Remote = 50MB
    mock_config.lfs_threshold_mb = 100
    mock_config.remote_storage_threshold_mb = 50

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "evidence").mkdir()
    (workspace / "evidence" / "assay_report.json").write_text("{}")

    # File size 75MB
    file_path = workspace / "medium.bin"
    file_size = 75 * 1024 * 1024

    # We mock stat because writing 75MB is slow/expensive in test
    original_stat = Path.stat
    target_path_str = str(file_path.absolute())

    def side_effect(self: Path, *args: Any, **kwargs: Any) -> object:
        if str(self.absolute()) == target_path_str:
            m = MagicMock()
            m.st_size = file_size
            # st_mode is needed for is_file check sometimes or other internal checks
            # but Path.is_file usually checks st_mode.
            # Let's rely on patching.
            # Note: Path.stat() is called. st_mode must indicate it is a file.
            m.st_mode = 33188  # typical regular file mode
            return m
        return original_stat(self, *args, **kwargs)

    # We need to create the file so rglob finds it
    file_path.touch()

    # Mock LFS finding files
    # LFS scan runs AFTER remote storage.
    # Remote storage replaces file with pointer (small).
    # So LFS scan should NOT find it as large file.
    # However, git_lfs.find_large_files uses os.walk/stat.
    # The artifact bundler calls `git_lfs.find_large_files`.
    # We need to ensure that when `find_large_files` is called, the file is already a pointer (small).
    # Since we are mocking `GitLFS`, we just assert `find_large_files` is called.
    # But to test the logic, we should assert what `find_large_files` *would* see if we weren't mocking it?
    # No, we verify flow.

    mock_storage_provider.upload.return_value = "hash-75"
    mock_git_lfs.is_initialized.return_value = True

    with patch("pathlib.Path.stat", side_effect=side_effect, autospec=True):
        artifact_bundler.bundle(workspace)

    # 1. Verify uploaded
    mock_storage_provider.upload.assert_called_once_with(file_path)

    # 2. Verify file content is pointer
    # Note: .bin is in MODEL_EXTENSIONS, so it gets moved to distilled/
    distilled_path = workspace / "models" / "distilled" / "medium.bin"
    assert distilled_path.exists()
    assert distilled_path.read_text() == "pointer:hash-75\n"
    assert not file_path.exists()

    # 3. Verify LFS scan called with threshold 100MB
    # Note: The bundler calls `git_lfs.find_large_files`.
    # It passes the workspace.
    # The bundler does NOT pass the file list to LFS. LFS finds them.
    # So we just check if it was called.
    mock_git_lfs.find_large_files.assert_called_with(workspace, 100 * 1024 * 1024)

    # Since the file is now a pointer (small), a real LFS scan would not find it.
    # And since we mocked `find_large_files` to return [], nothing is tracked.
    # This confirms that "Inverted Threshold" works: file is offloaded, pointer is small, LFS ignores pointer.


def test_zero_threshold_remote(
    artifact_bundler: ArtifactBundler, mock_storage_provider: MagicMock, mock_config: PublisherConfig, tmp_path: Path
) -> None:
    """Test setting remote storage threshold to 0 (upload everything)."""
    mock_config.remote_storage_threshold_mb = 0

    workspace = tmp_path / "workspace"
    workspace.mkdir()

    f1 = workspace / "f1.txt"
    f1.write_text("a")  # 1 byte

    mock_storage_provider.upload.return_value = "hash"

    artifact_bundler._handle_remote_storage(workspace)

    mock_storage_provider.upload.assert_called_once_with(f1)
    assert f1.read_text().startswith("pointer:")


def test_handle_remote_storage_permission_error(
    artifact_bundler: ArtifactBundler, mock_storage_provider: MagicMock, tmp_path: Path
) -> None:
    """
    Test handling of permission error when trying to write the pointer file.
    The upload happens, but writing pointer fails.
    Logic should probably fail or log error?
    Current code:
    try: ... upload ... write ... except OSError: log warning
    If write fails, we catch exception?

    The code has `try... except OSError` wrapping the loop body.
    So it should catch it and log warning.
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    f = workspace / "locked.bin"
    f.write_text("content")

    # Set threshold low to trigger
    artifact_bundler.config.remote_storage_threshold_mb = 0

    mock_storage_provider.upload.return_value = "hash"

    # Patch open to fail on write
    original_open = open

    def side_effect(file: Any, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        if str(file) == str(f) and "w" in mode:
            raise OSError("Write denied")
        return original_open(file, mode, *args, **kwargs)

    with patch("builtins.open", side_effect=side_effect):
        artifact_bundler._handle_remote_storage(workspace)

    # Upload was called
    mock_storage_provider.upload.assert_called()

    # File content should remain (since write failed)
    assert f.read_text() == "content"

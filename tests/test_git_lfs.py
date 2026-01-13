# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_publisher

import re
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from coreason_publisher.core.git_lfs import GitLFS


@pytest.fixture  # type: ignore[misc]
def git_lfs() -> GitLFS:
    return GitLFS()


def test_is_installed_true(git_lfs: GitLFS) -> None:
    with patch("shutil.which", return_value="/usr/bin/git-lfs"):
        assert git_lfs.is_installed() is True


def test_is_installed_false(git_lfs: GitLFS) -> None:
    with patch("shutil.which", return_value=None):
        assert git_lfs.is_installed() is False


def test_is_initialized_not_a_git_repo(git_lfs: GitLFS, tmp_path: Path) -> None:
    # tmp_path is just a directory, not a git repo
    assert git_lfs.is_initialized(tmp_path) is False


def test_is_initialized_success(git_lfs: GitLFS, tmp_path: Path) -> None:
    # We check 1. git rev-parse, 2. git lfs env
    # Patch subprocess.run where it is used
    with patch("coreason_publisher.core.git_lfs.subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0),
            MagicMock(returncode=0),
        ]
        assert git_lfs.is_initialized(tmp_path) is True
        assert mock_run.call_count == 2
        assert mock_run.call_args_list[0][0][0] == ["git", "rev-parse", "--is-inside-work-tree"]
        assert mock_run.call_args_list[1][0][0] == ["git", "lfs", "env"]


def test_is_initialized_failure(git_lfs: GitLFS, tmp_path: Path) -> None:
    # Fails at git rev-parse
    with patch("coreason_publisher.core.git_lfs.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=128, stderr="Not a git repository")
        assert git_lfs.is_initialized(tmp_path) is False


def test_is_initialized_lfs_failure(git_lfs: GitLFS, tmp_path: Path) -> None:
    # Fails at git lfs env
    with patch("coreason_publisher.core.git_lfs.subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0),
            MagicMock(returncode=1, stderr="LFS error"),
        ]
        assert git_lfs.is_initialized(tmp_path) is False


def test_is_initialized_exception(git_lfs: GitLFS, tmp_path: Path) -> None:
    with patch("coreason_publisher.core.git_lfs.subprocess.run", side_effect=Exception("Boom")):
        assert git_lfs.is_initialized(tmp_path) is False


def test_initialize_success(git_lfs: GitLFS, tmp_path: Path) -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        git_lfs.initialize(tmp_path)
        mock_run.assert_called_once_with(
            ["git", "lfs", "install"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
            text=True,
        )


def test_initialize_failure(git_lfs: GitLFS, tmp_path: Path) -> None:
    with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "cmd", stderr="error")):
        with pytest.raises(RuntimeError, match="Failed to initialize Git LFS"):
            git_lfs.initialize(tmp_path)


def test_track_patterns_empty(git_lfs: GitLFS, tmp_path: Path) -> None:
    with patch("subprocess.run") as mock_run:
        git_lfs.track_patterns(tmp_path, [])
        mock_run.assert_not_called()


def test_track_patterns_success(git_lfs: GitLFS, tmp_path: Path) -> None:
    patterns = ["*.bin", "*.pt"]
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        git_lfs.track_patterns(tmp_path, patterns)
        mock_run.assert_called_once_with(
            ["git", "lfs", "track", "*.bin", "*.pt"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
            text=True,
        )


def test_track_patterns_failure(git_lfs: GitLFS, tmp_path: Path) -> None:
    patterns = ["*.bin"]
    with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "cmd", stderr="error")):
        with pytest.raises(RuntimeError, match="Failed to track patterns"):
            git_lfs.track_patterns(tmp_path, patterns)


# --- Edge Case Tests ---


def test_track_patterns_special_characters(git_lfs: GitLFS, tmp_path: Path) -> None:
    """Test that special characters (spaces, glob patterns) are handled correctly."""
    patterns = ["file with spaces.bin", "model_v1[a-z].pt", "'quoted'.txt"]
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        git_lfs.track_patterns(tmp_path, patterns)

        # Verify the list arguments passed to subprocess (no shell escaping needed)
        expected_cmd = ["git", "lfs", "track", "file with spaces.bin", "model_v1[a-z].pt", "'quoted'.txt"]
        mock_run.assert_called_once_with(
            expected_cmd,
            cwd=tmp_path,
            check=True,
            capture_output=True,
            text=True,
        )


def test_initialize_git_executable_missing(git_lfs: GitLFS, tmp_path: Path) -> None:
    """Test that FileNotFoundError from subprocess (missing git) is caught and raised as RuntimeError."""
    with patch("subprocess.run", side_effect=FileNotFoundError):
        with pytest.raises(RuntimeError, match="Git executable not found"):
            git_lfs.initialize(tmp_path)


def test_track_patterns_git_executable_missing(git_lfs: GitLFS, tmp_path: Path) -> None:
    """Test that FileNotFoundError from subprocess (missing git) is caught and raised as RuntimeError."""
    patterns = ["*.bin"]
    with patch("subprocess.run", side_effect=FileNotFoundError):
        with pytest.raises(RuntimeError, match="Git executable not found"):
            git_lfs.track_patterns(tmp_path, patterns)


def test_find_large_files_mixed(git_lfs: GitLFS, tmp_path: Path) -> None:
    """Test identifying files larger than threshold."""
    # Create test files
    (tmp_path / "small.txt").write_text("small")

    large_file = tmp_path / "large.bin"
    # Write 1024 bytes
    with open(large_file, "wb") as f:
        f.write(b"\0" * 1024)

    nested_dir = tmp_path / "subdir"
    nested_dir.mkdir()
    (nested_dir / "nested_small.txt").write_text("small")

    nested_large = nested_dir / "nested_large.bin"
    with open(nested_large, "wb") as f:
        f.write(b"\0" * 2048)

    # Threshold 500 bytes. Should find large.bin and nested_large.bin
    found_files = git_lfs.find_large_files(tmp_path, 500)

    assert len(found_files) == 2
    assert "large.bin" in found_files
    assert "subdir/nested_large.bin" in found_files


def test_find_large_files_none(git_lfs: GitLFS, tmp_path: Path) -> None:
    """Test finding no files when all are small."""
    (tmp_path / "small.txt").write_text("small")
    found_files = git_lfs.find_large_files(tmp_path, 1000)
    assert found_files == []


def test_find_large_files_empty_dir(git_lfs: GitLFS, tmp_path: Path) -> None:
    """Test scanning empty directory."""
    found_files = git_lfs.find_large_files(tmp_path, 100)
    assert found_files == []


def test_find_large_files_missing_path(git_lfs: GitLFS, tmp_path: Path) -> None:
    """Test scanning a non-existent path."""
    found_files = git_lfs.find_large_files(tmp_path / "missing", 100)
    assert found_files == []


def test_find_large_files_symlink(git_lfs: GitLFS, tmp_path: Path) -> None:
    """Test that symlinks are ignored."""
    target = tmp_path / "target.bin"
    with open(target, "wb") as f:
        f.write(b"\0" * 1024)

    link = tmp_path / "link.bin"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("Symlinks not supported on this OS")

    # If we scan, we should find target.bin. If we counted link, we'd have duplicates or errors.
    # The code explicitly ignores symlinks.
    found_files = git_lfs.find_large_files(tmp_path, 500)
    assert "target.bin" in found_files
    assert "link.bin" not in found_files


def test_find_large_files_oserror_on_stat(git_lfs: GitLFS, tmp_path: Path) -> None:
    """Test handling of OSError when checking file size."""
    (tmp_path / "normal.txt").write_text("normal")

    # We need to mock stat() to raise OSError for one file but work for others if needed
    # Since rglob returns Path objects, we need to patch Path.stat or the iterator

    # Let's mock rglob to return a mock object that raises OSError on stat
    mock_path = MagicMock(spec=Path)
    mock_path.is_file.return_value = True
    mock_path.is_symlink.return_value = False
    mock_path.stat.side_effect = OSError("Permission denied")
    # Mypy complains about assigning to return_value of __str__
    mock_path.__str__.return_value = str(tmp_path / "protected.bin")  # type: ignore[attr-defined]

    with patch.object(Path, "rglob", return_value=[mock_path]):
        # Should catch OSError and log warning, returning empty list (or list of successful ones)
        found_files = git_lfs.find_large_files(tmp_path, 100)
        assert found_files == []


def test_find_large_files_general_exception(git_lfs: GitLFS, tmp_path: Path) -> None:
    """Test handling of general exception during scan."""
    with patch.object(Path, "rglob", side_effect=Exception("Disk error")):
        with pytest.raises(Exception, match="Disk error"):
            git_lfs.find_large_files(tmp_path, 100)


def test_find_large_files_boundary_conditions(git_lfs: GitLFS, tmp_path: Path) -> None:
    """
    Test boundary conditions for file size threshold.
    Files equal to threshold should NOT be included.
    Files greater than threshold SHOULD be included.
    """
    threshold = 100

    # Case 1: Just below threshold (99 bytes)
    file_below = tmp_path / "below.bin"
    with open(file_below, "wb") as f:
        f.write(b"\0" * (threshold - 1))

    # Case 2: Exactly at threshold (100 bytes)
    file_exact = tmp_path / "exact.bin"
    with open(file_exact, "wb") as f:
        f.write(b"\0" * threshold)

    # Case 3: Just above threshold (101 bytes)
    file_above = tmp_path / "above.bin"
    with open(file_above, "wb") as f:
        f.write(b"\0" * (threshold + 1))

    found_files = git_lfs.find_large_files(tmp_path, threshold)

    assert "below.bin" not in found_files
    assert "exact.bin" not in found_files
    assert "above.bin" in found_files
    assert len(found_files) == 1


def test_find_large_files_special_characters(git_lfs: GitLFS, tmp_path: Path) -> None:
    """Test scanning files with spaces, unicode, and other special characters."""
    # Setup directory structure
    special_dir = tmp_path / "special_dir"
    special_dir.mkdir()

    # Define filenames
    name_spaces = "file with spaces.bin"
    name_unicode = "café_model.bin"
    name_brackets = "model_[v1.0].bin"

    # Create files (large enough to be found)
    threshold = 50
    size = 100

    for name in [name_spaces, name_unicode, name_brackets]:
        file_path = special_dir / name
        with open(file_path, "wb") as f:
            f.write(b"\0" * size)

    found_files = git_lfs.find_large_files(tmp_path, threshold)

    # Check assertions
    assert f"special_dir/{name_spaces}" in found_files
    assert f"special_dir/{name_unicode}" in found_files
    assert f"special_dir/{name_brackets}" in found_files
    assert len(found_files) == 3


# --- verify_ready Tests ---


def test_verify_ready_success(git_lfs: GitLFS, tmp_path: Path) -> None:
    """
    Test that verify_ready passes when:
    1. Installed
    2. Initialized (is_inside_work_tree + git lfs env success)
    3. Hooks are present and correct
    4. Hooks are executable
    """
    with (
        patch.object(git_lfs, "is_installed", return_value=True),
        patch.object(git_lfs, "is_initialized", return_value=True),
        patch("coreason_publisher.core.git_lfs.subprocess.run") as mock_run,
        patch("pathlib.Path.read_text", return_value="#!/bin/sh\ngit-lfs push --stdin\n"),
        patch("pathlib.Path.exists", return_value=True),
        patch("os.access", return_value=True),  # executable check
    ):
        # Mock git rev-parse --git-dir
        mock_run.return_value = MagicMock(returncode=0, stdout=".git\n")

        git_lfs.verify_ready(tmp_path)  # Should not raise


def test_verify_ready_not_installed(git_lfs: GitLFS, tmp_path: Path) -> None:
    """Test that verify_ready raises RuntimeError when not installed."""
    with patch.object(git_lfs, "is_installed", return_value=False):
        with pytest.raises(RuntimeError, match="Git LFS is not installed on the system"):
            git_lfs.verify_ready(tmp_path)


def test_verify_ready_not_initialized(git_lfs: GitLFS, tmp_path: Path) -> None:
    """Test that verify_ready raises RuntimeError when not initialized."""
    with (
        patch.object(git_lfs, "is_installed", return_value=True),
        patch.object(git_lfs, "is_initialized", return_value=False),
    ):
        # Escape path for regex matching on Windows
        escaped_path = re.escape(str(tmp_path))
        with pytest.raises(RuntimeError, match=f"Git LFS is not initialized in {escaped_path}"):
            git_lfs.verify_ready(tmp_path)


def test_verify_ready_missing_hooks(git_lfs: GitLFS, tmp_path: Path) -> None:
    """Test verify_ready raises RuntimeError when hooks are missing."""
    with (
        patch.object(git_lfs, "is_installed", return_value=True),
        patch.object(git_lfs, "is_initialized", return_value=True),
        patch("coreason_publisher.core.git_lfs.subprocess.run") as mock_run,
        patch("pathlib.Path.exists", return_value=False),  # hook missing
    ):
        # Mock git rev-parse --git-dir
        mock_run.return_value = MagicMock(returncode=0, stdout=".git\n")

        with pytest.raises(RuntimeError, match="Git LFS pre-push hook is missing"):
            git_lfs.verify_ready(tmp_path)


def test_verify_ready_broken_hooks(git_lfs: GitLFS, tmp_path: Path) -> None:
    """Test verify_ready raises RuntimeError when hook content is invalid."""
    with (
        patch.object(git_lfs, "is_installed", return_value=True),
        patch.object(git_lfs, "is_initialized", return_value=True),
        patch("coreason_publisher.core.git_lfs.subprocess.run") as mock_run,
        patch("pathlib.Path.exists", return_value=True),  # hook exists
        patch("pathlib.Path.read_text", return_value="#!/bin/sh\necho 'hello'\n"),  # Invalid content
    ):
        # Mock git rev-parse --git-dir
        mock_run.return_value = MagicMock(returncode=0, stdout=".git\n")

        with pytest.raises(RuntimeError, match="Git LFS pre-push hook exists but does not appear to call git-lfs"):
            git_lfs.verify_ready(tmp_path)


def test_verify_ready_hook_not_executable(git_lfs: GitLFS, tmp_path: Path) -> None:
    """Test verify_ready raises RuntimeError when hook is not executable."""
    with (
        patch.object(git_lfs, "is_installed", return_value=True),
        patch.object(git_lfs, "is_initialized", return_value=True),
        patch("coreason_publisher.core.git_lfs.subprocess.run") as mock_run,
        patch("pathlib.Path.exists", return_value=True),  # hook exists
        patch("pathlib.Path.read_text", return_value="#!/bin/sh\ngit-lfs push --stdin\n"),  # Valid content
        patch("os.access", return_value=False),  # NOT executable
    ):
        # Mock git rev-parse --git-dir
        mock_run.return_value = MagicMock(returncode=0, stdout=".git\n")

        with pytest.raises(RuntimeError, match="Git LFS pre-push hook is not executable"):
            git_lfs.verify_ready(tmp_path)


def test_verify_ready_git_dir_failure(git_lfs: GitLFS, tmp_path: Path) -> None:
    """Test verify_ready raises RuntimeError when git rev-parse fails."""
    with (
        patch.object(git_lfs, "is_installed", return_value=True),
        patch.object(git_lfs, "is_initialized", return_value=True),
        patch("coreason_publisher.core.git_lfs.subprocess.run") as mock_run,
    ):
        # Mock git rev-parse --git-dir failing
        mock_run.side_effect = subprocess.CalledProcessError(1, ["git", "rev-parse"])

        with pytest.raises(RuntimeError, match="Failed to determine git directory"):
            git_lfs.verify_ready(tmp_path)


def test_verify_ready_os_error(git_lfs: GitLFS, tmp_path: Path) -> None:
    """Test verify_ready raises RuntimeError when OSError occurs during file ops."""
    with (
        patch.object(git_lfs, "is_installed", return_value=True),
        patch.object(git_lfs, "is_initialized", return_value=True),
        patch("coreason_publisher.core.git_lfs.subprocess.run") as mock_run,
        patch("pathlib.Path.exists", side_effect=OSError("Disk read error")),
    ):
        # Mock git rev-parse --git-dir passing
        mock_run.return_value = MagicMock(returncode=0, stdout=".git\n")

        with pytest.raises(RuntimeError, match="Failed to verify hooks"):
            git_lfs.verify_ready(tmp_path)


def test_verify_ready_subdirectory(git_lfs: GitLFS, tmp_path: Path) -> None:
    """
    Test verify_ready works correctly in a subdirectory.
    is_initialized should pass (mocked), and verify_ready should find git dir via rev-parse.
    """
    subdir = tmp_path / "subdir"
    subdir.mkdir()

    with (
        patch.object(git_lfs, "is_installed", return_value=True),
        patch.object(git_lfs, "is_initialized", return_value=True),
        patch("coreason_publisher.core.git_lfs.subprocess.run") as mock_run,
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_text", return_value="git-lfs"),
        patch("os.access", return_value=True),  # executable
    ):
        # Mock git rev-parse --git-dir returning absolute or relative path to .git
        # If in subdir, git dir is ../.git usually.
        mock_run.return_value = MagicMock(returncode=0, stdout="../.git\n")

        git_lfs.verify_ready(subdir)  # Should not raise


def test_is_initialized_in_subdirectory(git_lfs: GitLFS, tmp_path: Path) -> None:
    """
    Verify that is_initialized uses git rev-parse --is-inside-work-tree
    to support subdirectories, rather than checking for .git folder directly.
    """
    subdir = tmp_path / "subdir"
    subdir.mkdir()

    # We mock subprocess.run to simulate git responses
    with patch("coreason_publisher.core.git_lfs.subprocess.run") as mock_run:
        # Sequence of calls:
        # 1. git rev-parse --is-inside-work-tree -> 0
        # 2. git lfs env -> 0

        mock_run.side_effect = [
            MagicMock(returncode=0),  # rev-parse
            MagicMock(returncode=0),  # lfs env
        ]

        assert git_lfs.is_initialized(subdir) is True
        assert mock_run.call_count == 2
        # Verify first call args check for rev-parse
        assert mock_run.call_args_list[0][0][0] == ["git", "rev-parse", "--is-inside-work-tree"]

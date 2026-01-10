# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_publisher

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
    (tmp_path / ".git").mkdir()
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        assert git_lfs.is_initialized(tmp_path) is True
        mock_run.assert_called_once_with(
            ["git", "lfs", "env"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
        )


def test_is_initialized_failure(git_lfs: GitLFS, tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr="Not a git repository")
        assert git_lfs.is_initialized(tmp_path) is False


def test_is_initialized_exception(git_lfs: GitLFS, tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    with patch("subprocess.run", side_effect=Exception("Boom")):
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

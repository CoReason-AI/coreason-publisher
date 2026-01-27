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
from git import Repo
from git.exc import GitCommandError

from coreason_publisher.core.git_local import GitLocal

# Existing integration-style tests


@pytest.fixture
def temp_git_repo(tmp_path: Path) -> Path:
    """Creates a temporary git repository."""
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()
    repo = Repo.init(repo_dir)

    # Configure user for commits
    repo.config_writer().set_value("user", "name", "Test User").release()
    repo.config_writer().set_value("user", "email", "test@example.com").release()

    # Create initial commit
    (repo_dir / "README.md").write_text("Initial commit")
    repo.index.add(["README.md"])
    repo.index.commit("Initial commit")

    return repo_dir


def test_init_invalid_repo(tmp_path: Path) -> None:
    """Test initialization with an invalid repository path."""
    with pytest.raises(ValueError, match="Invalid git repository"):
        GitLocal(tmp_path)


def test_checkout_new_branch(temp_git_repo: Path) -> None:
    """Test creating and checking out a new branch."""
    git_local = GitLocal(temp_git_repo)
    new_branch = "feature/test-branch"

    git_local.checkout_new_branch(new_branch)

    assert git_local.get_current_branch() == new_branch
    repo = Repo(temp_git_repo)
    assert new_branch in repo.heads


def test_checkout_existing_branch(temp_git_repo: Path) -> None:
    """Test checking out an existing branch."""
    git_local = GitLocal(temp_git_repo)
    repo = Repo(temp_git_repo)

    # Create a branch manually
    repo.create_head("existing-branch")

    git_local.checkout_branch("existing-branch")
    assert git_local.get_current_branch() == "existing-branch"


def test_checkout_existing_branch_via_new(temp_git_repo: Path) -> None:
    """Test that checkout_new_branch handles existing branches gracefully."""
    git_local = GitLocal(temp_git_repo)
    repo = Repo(temp_git_repo)

    # Create a branch manually
    branch_name = "existing-branch"
    repo.create_head(branch_name)

    # Should switch to it, not crash
    git_local.checkout_new_branch(branch_name)
    assert git_local.get_current_branch() == branch_name


def test_checkout_nonexistent_branch(temp_git_repo: Path) -> None:
    """Test checking out a branch that does not exist."""
    git_local = GitLocal(temp_git_repo)

    with pytest.raises(ValueError, match="does not exist locally"):
        git_local.checkout_branch("non-existent")


def test_add_all_and_commit(temp_git_repo: Path) -> None:
    """Test adding and committing files."""
    git_local = GitLocal(temp_git_repo)

    # Create a new file
    new_file = temp_git_repo / "new_file.txt"
    new_file.write_text("Hello World")

    assert git_local.is_dirty()

    git_local.add_all()
    git_local.commit("Add new file")

    assert not git_local.is_dirty()

    repo = Repo(temp_git_repo)
    last_commit = repo.head.commit
    assert last_commit.message == "Add new file"
    assert "new_file.txt" in last_commit.tree


def test_push(temp_git_repo: Path, tmp_path: Path) -> None:
    """Test pushing to a remote."""
    # Create a bare repo to act as remote
    remote_dir = tmp_path / "remote_repo"
    Repo.init(remote_dir, bare=True)

    # Add remote to local repo
    repo = Repo(temp_git_repo)
    repo.create_remote("origin", str(remote_dir))

    git_local = GitLocal(temp_git_repo)

    # Create new branch and push
    git_local.checkout_new_branch("feature/push-test")

    # Modify file and commit so we have something to push
    (temp_git_repo / "README.md").write_text("Update")
    git_local.add_all()
    git_local.commit("Update")

    git_local.push("feature/push-test")

    # Verify ref exists in remote
    remote_repo = Repo(remote_dir)
    assert "feature/push-test" in remote_repo.heads


def test_push_invalid_remote(temp_git_repo: Path) -> None:
    """Test pushing to a non-existent remote."""
    git_local = GitLocal(temp_git_repo)

    with pytest.raises(ValueError, match="Remote origin not found"):
        git_local.push("master")


# Mock tests for error coverage


def test_checkout_new_branch_error(temp_git_repo: Path) -> None:
    """Test error handling in checkout_new_branch."""
    git_local = GitLocal(temp_git_repo)

    # Mock the internal repo object
    git_local.repo = MagicMock()
    # Heads mock needs to not have the branch
    git_local.repo.heads = {}
    git_local.repo.create_head.side_effect = GitCommandError("checkout", 128)

    with pytest.raises(RuntimeError, match="Failed to checkout branch"):
        git_local.checkout_new_branch("new-branch")


def test_checkout_branch_error(temp_git_repo: Path) -> None:
    """Test error handling in checkout_branch."""
    git_local = GitLocal(temp_git_repo)

    git_local.repo = MagicMock()
    # Simulate branch exists in heads but checkout fails
    mock_head = MagicMock()
    mock_head.checkout.side_effect = GitCommandError("checkout", 128)
    git_local.repo.heads = {"existing": mock_head}

    with pytest.raises(RuntimeError, match="Failed to checkout branch"):
        git_local.checkout_branch("existing")


def test_add_all_error(temp_git_repo: Path) -> None:
    """Test error handling in add_all."""
    git_local = GitLocal(temp_git_repo)

    git_local.repo = MagicMock()
    git_local.repo.git.add.side_effect = GitCommandError("add", 128)

    with pytest.raises(RuntimeError, match="Failed to stage files"):
        git_local.add_all()


def test_commit_error(temp_git_repo: Path) -> None:
    """Test error handling in commit."""
    git_local = GitLocal(temp_git_repo)

    git_local.repo = MagicMock()
    git_local.repo.index.commit.side_effect = GitCommandError("commit", 128)

    with pytest.raises(RuntimeError, match="Failed to commit"):
        git_local.commit("msg")


def test_push_error(temp_git_repo: Path) -> None:
    """Test error handling in push."""
    git_local = GitLocal(temp_git_repo)

    git_local.repo = MagicMock()
    mock_remote = MagicMock()
    mock_remote.push.side_effect = GitCommandError("push", 128)
    git_local.repo.remote.return_value = mock_remote

    with pytest.raises(RuntimeError, match="Failed to push"):
        git_local.push("branch")


def test_get_current_branch_detached(temp_git_repo: Path) -> None:
    """Test get_current_branch when in detached HEAD state."""
    git_local = GitLocal(temp_git_repo)

    # Checkout a commit hash to detach HEAD
    repo = Repo(temp_git_repo)
    commit = repo.head.commit
    repo.git.checkout(commit.hexsha)

    assert git_local.get_current_branch() == "detached"

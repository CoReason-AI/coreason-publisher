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

import pytest
from git import Repo

from coreason_publisher.core.git_local import GitLocal


@pytest.fixture
def temp_git_repo(tmp_path: Path) -> Path:
    """Creates a temporary git repository."""
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()
    repo = Repo.init(repo_dir)

    repo.config_writer().set_value("user", "name", "Test User").release()
    repo.config_writer().set_value("user", "email", "test@example.com").release()

    (repo_dir / "README.md").write_text("Initial commit")
    repo.index.add(["README.md"])
    repo.index.commit("Initial commit")

    return repo_dir


def test_commit_no_changes(temp_git_repo: Path) -> None:
    """Test behavior when trying to commit with no changes staged."""
    git_local = GitLocal(temp_git_repo)

    # No changes made
    git_local.add_all()

    # By default, GitPython's index.commit usually proceeds but might create empty commit or fail?
    # CLI `git commit` fails without --allow-empty.
    # index.commit writes a tree. If tree is same as parent, it's an empty commit.

    # We expect it to SUCCEED and create an empty commit (which is fine for Orchestrator,
    # though usually we'd want to avoid it. If it fails, we need to handle it).

    try:
        git_local.commit("Empty commit")
    except RuntimeError:
        pytest.fail("Commit failed for no changes")

    repo = Repo(temp_git_repo)
    # Check if new commit was created
    assert repo.head.commit.message == "Empty commit"
    # It should be an empty commit (tree same as parent)
    assert repo.head.commit.tree == repo.head.commit.parents[0].tree


def test_checkout_conflict_dirty_worktree(temp_git_repo: Path) -> None:
    """Test checking out a branch when a local file conflicts."""
    git_local = GitLocal(temp_git_repo)
    repo = Repo(temp_git_repo)

    # Create a branch 'feature'
    repo.create_head("feature")

    # Create a file in 'feature' that doesn't exist in 'master'
    repo.heads["feature"].checkout()
    (temp_git_repo / "conflict.txt").write_text("Feature content")
    repo.index.add(["conflict.txt"])
    repo.index.commit("Add conflict file")

    # Go back to master
    repo.heads["master"].checkout()

    # Now create untracked file 'conflict.txt' in master
    (temp_git_repo / "conflict.txt").write_text("Local content")

    # Try to checkout 'feature'. git should refuse because it would overwrite untracked file.
    with pytest.raises(RuntimeError, match="Failed to checkout branch"):
        git_local.checkout_branch("feature")

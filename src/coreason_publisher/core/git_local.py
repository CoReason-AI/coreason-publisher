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

from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

from coreason_publisher.utils.logger import logger


class GitLocal:
    """
    Wrapper for local Git operations using GitPython.
    Handles repository initialization, branching, committing, and pushing.
    """

    def __init__(self, repo_path: Path) -> None:
        """
        Initialize the GitLocal wrapper.

        Args:
            repo_path: Path to the root of the git repository.
        """
        self.repo_path = repo_path
        try:
            self.repo = Repo(repo_path)
        except InvalidGitRepositoryError as e:
            logger.error(f"Invalid git repository at {repo_path}")
            raise ValueError(f"Invalid git repository at {repo_path}") from e

    def checkout_new_branch(self, branch_name: str) -> None:
        """
        Creates and checks out a new branch.

        Args:
            branch_name: The name of the new branch.
        """
        logger.info(f"Creating and checking out new branch: {branch_name}")
        try:
            current = self.repo.active_branch
            # Check if branch exists
            if branch_name in self.repo.heads:
                logger.warning(f"Branch {branch_name} already exists. Checking it out.")
                self.repo.heads[branch_name].checkout()
            else:
                self.repo.create_head(branch_name, current).checkout()
        except GitCommandError as e:
            logger.error(f"Failed to checkout branch {branch_name}: {e}")
            raise RuntimeError(f"Failed to checkout branch {branch_name}: {e}") from e

    def checkout_branch(self, branch_name: str) -> None:
        """
        Checks out an existing branch.

        Args:
            branch_name: The name of the branch to checkout.
        """
        logger.info(f"Checking out branch: {branch_name}")
        try:
            if branch_name not in self.repo.heads:
                # Try to fetch if not local? For now, assume local existence or strict requirement.
                # If it's a remote branch, we might need to handle it differently, but "checkout_branch" usually implies local.
                logger.error(f"Branch {branch_name} does not exist locally.")
                raise ValueError(f"Branch {branch_name} does not exist locally.")

            self.repo.heads[branch_name].checkout()
        except GitCommandError as e:
            logger.error(f"Failed to checkout branch {branch_name}: {e}")
            raise RuntimeError(f"Failed to checkout branch {branch_name}: {e}") from e

    def add_all(self) -> None:
        """Stages all changes (equivalent to `git add .`)."""
        logger.info("Staging all changes")
        try:
            self.repo.git.add(A=True)
        except GitCommandError as e:
            logger.error(f"Failed to stage files: {e}")
            raise RuntimeError(f"Failed to stage files: {e}") from e

    def commit(self, message: str) -> None:
        """
        Commits staged changes.

        Args:
            message: The commit message.
        """
        logger.info(f"Committing changes with message: {message}")
        try:
            self.repo.index.commit(message)
        except GitCommandError as e:
            logger.error(f"Failed to commit: {e}")
            raise RuntimeError(f"Failed to commit: {e}") from e

    def push(self, branch_name: str, remote_name: str = "origin") -> None:
        """
        Pushes the branch to the remote.

        Args:
            branch_name: The name of the branch to push.
            remote_name: The name of the remote (default: origin).
        """
        logger.info(f"Pushing {branch_name} to {remote_name}")
        try:
            remote = self.repo.remote(name=remote_name)
            remote.push(refspec=f"{branch_name}:{branch_name}", set_upstream=True)
        except ValueError:
            logger.error(f"Remote {remote_name} not found")
            raise ValueError(f"Remote {remote_name} not found")
        except GitCommandError as e:
            logger.error(f"Failed to push {branch_name}: {e}")
            raise RuntimeError(f"Failed to push {branch_name}: {e}") from e

    def is_dirty(self) -> bool:
        """Checks if the working directory has uncommitted changes."""
        return self.repo.is_dirty(untracked_files=True)

    def get_current_branch(self) -> str:
        """Returns the name of the current active branch."""
        try:
            return str(self.repo.active_branch.name)
        except TypeError:
            # Detached HEAD state
            return "detached"

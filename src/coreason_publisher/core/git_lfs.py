# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_publisher

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import List

from coreason_publisher.utils.logger import logger


class GitLFS:
    """Wrapper around git-lfs CLI."""

    def is_installed(self) -> bool:
        """Checks if git-lfs is installed on the system."""
        return shutil.which("git-lfs") is not None

    def is_initialized(self, repo_path: Path) -> bool:
        """
        Checks if git-lfs is initialized in the given repository.

        We check this by seeing if `git lfs env` returns successfully
        AND verifying the endpoint configuration.
        """
        try:
            # Check if it is a git repo first by running a git command,
            # which works even in subdirectories.
            is_git_check = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=False,
            )
            if is_git_check.returncode != 0:
                logger.error(f"{repo_path} is not inside a git work tree.")
                return False

            result = subprocess.run(
                ["git", "lfs", "env"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                logger.debug(f"git lfs env failed: {result.stderr}")
                return False

            # Verify endpoint configuration
            # Looking for something like 'Endpoint=https://...' or 'Endpoint (git)=https://...'
            # Simply checking if "Endpoint" is in the output is a reasonable proxy for configuration check.
            if "Endpoint" not in result.stdout:
                logger.error("Git LFS environment does not show a configured Endpoint.")
                return False

            return True
        except Exception as e:
            logger.exception(f"Error checking LFS initialization: {e}")
            return False

    def verify_ready(self, repo_path: Path) -> None:
        """
        Verifies that Git LFS is installed, initialized, AND hooks are present.

        Args:
            repo_path: The path to the repository to check.

        Raises:
            RuntimeError: If Git LFS is not installed, not initialized, or hooks are missing.
        """
        if not self.is_installed():
            logger.error("Git LFS is not installed on the system.")
            raise RuntimeError("Git LFS is not installed on the system.")

        if not self.is_initialized(repo_path):
            logger.error(f"Git LFS is not initialized in {repo_path}.")
            raise RuntimeError(f"Git LFS is not initialized in {repo_path}.")

        # Deep verification: Check for pre-push hook
        try:
            # Get hooks directory using --git-path (handles worktrees/submodules correctly)
            hooks_path_proc = subprocess.run(
                ["git", "rev-parse", "--git-path", "hooks"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            hooks_path_str = hooks_path_proc.stdout.strip()

            # Resolve path (relative to repo root or absolute)
            if Path(hooks_path_str).is_absolute():
                hooks_dir = Path(hooks_path_str)
            else:
                hooks_dir = repo_path / hooks_path_str
                # Normalize path
                hooks_dir = hooks_dir.resolve()

            pre_push_hook = hooks_dir / "pre-push"

            if not pre_push_hook.exists():
                logger.error(f"LFS pre-push hook missing at {pre_push_hook}")
                raise RuntimeError("Git LFS pre-push hook is missing. Run 'git lfs install'.")

            # Check content
            content = pre_push_hook.read_text(encoding="utf-8", errors="ignore")
            if "git-lfs" not in content and "git lfs" not in content:
                logger.error(f"LFS pre-push hook at {pre_push_hook} does not seem to call git-lfs")
                raise RuntimeError("Git LFS pre-push hook exists but does not appear to call git-lfs.")

            # Check executability
            if not os.access(pre_push_hook, os.X_OK):
                logger.error(f"LFS pre-push hook at {pre_push_hook} is not executable")
                raise RuntimeError("Git LFS pre-push hook is not executable. Run 'chmod +x .git/hooks/pre-push'.")

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to determine git directory: {e}")
            raise RuntimeError(f"Failed to determine git directory: {e}") from e
        except OSError as e:
            logger.error(f"Failed to verify hooks: {e}")
            raise RuntimeError(f"Failed to verify hooks: {e}") from e

        logger.info(f"Git LFS is verified ready (env + hooks) in {repo_path}")

    def initialize(self, repo_path: Path) -> None:
        """Initializes git-lfs in the repository."""
        logger.info(f"Initializing Git LFS in {repo_path}")
        try:
            subprocess.run(
                ["git", "lfs", "install"],
                cwd=repo_path,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to initialize Git LFS: {e.stderr}")
            raise RuntimeError(f"Failed to initialize Git LFS: {e.stderr}") from e
        except FileNotFoundError as e:
            logger.error("Git executable not found")
            raise RuntimeError("Git executable not found") from e

    def find_large_files(self, search_path: Path, threshold_bytes: int) -> List[str]:
        """
        Recursively finds files in the search path larger than the threshold.

        Args:
            search_path: The root directory to search.
            threshold_bytes: The size threshold in bytes.

        Returns:
            A list of file paths relative to search_path.
        """
        large_files: List[str] = []
        logger.info(f"Scanning {search_path} for files larger than {threshold_bytes} bytes")

        if not search_path.exists():
            logger.warning(f"Search path does not exist: {search_path}")
            return []

        try:
            for file_path in search_path.rglob("*"):
                try:
                    if file_path.is_file() and not file_path.is_symlink():
                        # Exclude .git directory from scan to match robust behavior
                        if ".git" in file_path.parts:
                            continue

                        if file_path.stat().st_size > threshold_bytes:
                            # Use relative path for cleaner tracking
                            relative_path = file_path.relative_to(search_path).as_posix()
                            large_files.append(relative_path)
                except OSError as e:
                    logger.warning(f"Could not check file size for {file_path}: {e}")
        except Exception as e:
            logger.error(f"Error during large file scan: {e}")
            raise

        return large_files

    def track_patterns(self, repo_path: Path, patterns: List[str]) -> None:
        """
        Tracks the given file patterns using git-lfs.
        Ensures idempotency by checking .gitattributes first.
        """
        if not patterns:
            return

        # Check existing .gitattributes to avoid redundant calls
        gitattributes_path = repo_path / ".gitattributes"
        existing_attributes = ""
        if gitattributes_path.exists():
            try:
                existing_attributes = gitattributes_path.read_text(encoding="utf-8", errors="ignore")
            except Exception as e:
                logger.warning(f"Failed to read .gitattributes: {e}")

        # Filter patterns that are not already tracked
        new_patterns = []
        for pattern in patterns:
            # Simple check: if pattern + " filter=lfs" is in attributes.
            # Use regex for better accuracy (allow spaces, etc.)
            # Pattern in .gitattributes usually looks like: pattern filter=lfs diff=lfs merge=lfs -text
            # We just search for the pattern at start of line
            escaped_pattern = re.escape(pattern)
            # This regex might be too strict if user has custom attributes,
            # but sufficient for idempotency check of our own actions.
            if not re.search(rf"^{escaped_pattern}\s+filter=lfs", existing_attributes, re.MULTILINE):
                new_patterns.append(pattern)
            else:
                logger.debug(f"Pattern '{pattern}' is already tracked in .gitattributes")

        if not new_patterns:
            logger.info("All patterns are already tracked.")
            return

        logger.info(f"Tracking new patterns with Git LFS: {new_patterns}")
        try:
            cmd = ["git", "lfs", "track"] + new_patterns
            subprocess.run(
                cmd,
                cwd=repo_path,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to track patterns: {e.stderr}")
            raise RuntimeError(f"Failed to track patterns: {e.stderr}") from e
        except FileNotFoundError as e:
            logger.error("Git executable not found")
            raise RuntimeError("Git executable not found") from e

# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_publisher

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

        We check this by seeing if `git lfs env` returns successfully.
        """
        try:
            # Check if it is a git repo first
            if not (repo_path / ".git").exists():
                logger.error(f"{repo_path} is not a git repository.")
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

            return True
        except Exception as e:
            logger.exception(f"Error checking LFS initialization: {e}")
            return False

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

    def track_patterns(self, repo_path: Path, patterns: List[str]) -> None:
        """Tracks the given file patterns using git-lfs."""
        if not patterns:
            return

        logger.info(f"Tracking patterns with Git LFS: {patterns}")
        try:
            cmd = ["git", "lfs", "track"] + patterns
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

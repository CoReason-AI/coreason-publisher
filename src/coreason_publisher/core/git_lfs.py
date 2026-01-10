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
        except FileNotFoundError as e:
            logger.error("Git executable not found")
            raise RuntimeError("Git executable not found") from e

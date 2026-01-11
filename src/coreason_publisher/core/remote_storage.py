# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_publisher

from abc import ABC, abstractmethod
from pathlib import Path

from coreason_publisher.utils.logger import logger


class RemoteStorageProvider(ABC):
    """Abstract base class for remote storage providers (S3, Artifactory, etc.)."""

    @abstractmethod
    def upload(self, file_path: Path) -> str:
        """
        Uploads a file to remote storage.

        Args:
            file_path: The local path to the file.

        Returns:
            A unique identifier (e.g., hash or URL) for the stored file.
        """
        pass  # pragma: no cover


class MockStorageProvider(RemoteStorageProvider):
    """Mock implementation of RemoteStorageProvider for testing and dev."""

    def upload(self, file_path: Path) -> str:
        """Simulates an upload."""
        logger.info(f"Mock uploading {file_path} to remote storage...")
        # In a real implementation, we might hash the file content here.
        # For now, we just return a dummy hash.
        return f"mock-hash-{file_path.name}"

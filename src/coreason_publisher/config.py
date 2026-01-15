# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_publisher

from dataclasses import dataclass


@dataclass
class PublisherConfig:
    """Configuration for the Coreason Publisher."""

    lfs_threshold_mb: int = 100
    # 70GB default
    remote_storage_threshold_mb: int = 70 * 1024

    @property
    def lfs_threshold_bytes(self) -> int:
        """Returns the LFS threshold in bytes."""
        return self.lfs_threshold_mb * 1024 * 1024

    @property
    def remote_storage_threshold_bytes(self) -> int:
        """Returns the remote storage threshold in bytes."""
        return self.remote_storage_threshold_mb * 1024 * 1024

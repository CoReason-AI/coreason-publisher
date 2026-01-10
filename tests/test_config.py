# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_publisher

from coreason_publisher.config import PublisherConfig


def test_publisher_config_defaults() -> None:
    config = PublisherConfig()
    assert config.lfs_threshold_mb == 100
    assert config.lfs_threshold_bytes == 100 * 1024 * 1024


def test_publisher_config_custom() -> None:
    config = PublisherConfig(lfs_threshold_mb=50)
    assert config.lfs_threshold_mb == 50
    assert config.lfs_threshold_bytes == 50 * 1024 * 1024

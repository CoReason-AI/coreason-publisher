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

from coreason_publisher.core.remote_storage import MockStorageProvider


def test_mock_storage_provider_upload(tmp_path: Path) -> None:
    """Test MockStorageProvider upload simulation."""
    provider = MockStorageProvider()

    file_path = tmp_path / "test_file.bin"
    file_path.touch()

    result = provider.upload(file_path)

    assert result == "mock-hash-test_file.bin"

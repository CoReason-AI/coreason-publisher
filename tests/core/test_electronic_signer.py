# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_publisher

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from coreason_publisher.core.electronic_signer import ElectronicSigner


@pytest.fixture  # type: ignore[misc]
def signer() -> ElectronicSigner:
    return ElectronicSigner()


def test_calculate_bundle_hash_deterministic(signer: ElectronicSigner, tmp_path: Path) -> None:
    """Test that hashing is deterministic for the same content."""
    # Setup two identical directories
    dir1 = tmp_path / "dir1"
    dir1.mkdir()
    (dir1 / "file1.txt").write_text("content1")
    (dir1 / "file2.txt").write_text("content2")

    dir2 = tmp_path / "dir2"
    dir2.mkdir()
    (dir2 / "file1.txt").write_text("content1")
    (dir2 / "file2.txt").write_text("content2")

    hash1 = signer.calculate_bundle_hash(dir1)
    hash2 = signer.calculate_bundle_hash(dir2)

    assert hash1 == hash2


def test_calculate_bundle_hash_sensitivity(signer: ElectronicSigner, tmp_path: Path) -> None:
    """Test that changing file content changes the hash."""
    dir1 = tmp_path / "dir1"
    dir1.mkdir()
    file1 = dir1 / "file1.txt"
    file1.write_text("content1")

    hash1 = signer.calculate_bundle_hash(dir1)

    # Modify content
    file1.write_text("content1_modified")
    hash2 = signer.calculate_bundle_hash(dir1)

    assert hash1 != hash2


def test_calculate_bundle_hash_filename_sensitivity(signer: ElectronicSigner, tmp_path: Path) -> None:
    """Test that changing filename changes the hash."""
    dir1 = tmp_path / "dir1"
    dir1.mkdir()
    (dir1 / "file1.txt").write_text("content1")
    hash1 = signer.calculate_bundle_hash(dir1)

    # Rename file
    (dir1 / "file1.txt").rename(dir1 / "file2.txt")
    hash2 = signer.calculate_bundle_hash(dir1)

    assert hash1 != hash2


def test_calculate_bundle_hash_excludes_git(signer: ElectronicSigner, tmp_path: Path) -> None:
    """Test that .git directory is excluded from hashing."""
    dir1 = tmp_path / "dir1"
    dir1.mkdir()
    (dir1 / "file1.txt").write_text("content1")

    hash1 = signer.calculate_bundle_hash(dir1)

    # Add .git directory and file inside it
    git_dir = dir1 / ".git"
    git_dir.mkdir()
    (git_dir / "index").write_text("git data")

    hash2 = signer.calculate_bundle_hash(dir1)

    assert hash1 == hash2


def test_calculate_bundle_hash_missing_path(signer: ElectronicSigner, tmp_path: Path) -> None:
    """Test that hashing a non-existent path raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        signer.calculate_bundle_hash(tmp_path / "nonexistent")


def test_calculate_bundle_hash_read_error(signer: ElectronicSigner, tmp_path: Path) -> None:
    """Test that a file read error raises RuntimeError."""
    dir1 = tmp_path / "dir1"
    dir1.mkdir()
    file1 = dir1 / "file1.txt"
    file1.write_text("content")

    # Mock open to raise OSError
    with patch("builtins.open", side_effect=OSError("Mocked error")):
        with pytest.raises(RuntimeError) as excinfo:
            signer.calculate_bundle_hash(dir1)

        assert "Failed to read file" in str(excinfo.value)


def test_create_and_verify_signature(signer: ElectronicSigner, tmp_path: Path) -> None:
    """Test the signature creation and verification flow."""
    dir1 = tmp_path / "dir1"
    dir1.mkdir()
    (dir1 / "file1.txt").write_text("content")

    sig = signer.create_signature(dir1, "user123")
    assert signer.verify_signature(dir1, sig)

    # Modify content and verify failure
    (dir1 / "file1.txt").write_text("modified")
    assert not signer.verify_signature(dir1, sig)


def test_format_commit_message(signer: ElectronicSigner) -> None:
    """Test that the commit message is formatted correctly with audit trail."""
    original_msg = "feat: add new model"
    user_id = "user123"
    role = "SRE"
    signature = "abcdef123456"

    formatted = signer.format_commit_message(original_msg, user_id, signature, role)

    assert original_msg in formatted
    assert "--- COREASON AUDIT TRAIL ---" in formatted
    assert user_id in formatted
    assert role in formatted
    assert signature in formatted

    # Check if JSON is valid
    start_marker = "--- COREASON AUDIT TRAIL ---\n"
    end_marker = "\n----------------------------"
    start_idx = formatted.find(start_marker) + len(start_marker)
    end_idx = formatted.find(end_marker)

    json_str = formatted[start_idx:end_idx]
    data = json.loads(json_str)

    assert data["signer_id"] == user_id
    assert data["signature"] == signature
    assert data["compliance"] == "21 CFR Part 11"


def test_send_audit_to_veritas(signer: ElectronicSigner) -> None:
    """Test the stub for sending audit data to Veritas."""
    # Just call it to ensure no exceptions and coverage
    signer.send_audit_to_veritas("user123", "sig123", "SRE")

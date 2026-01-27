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
from pathlib import Path

import pytest

from coreason_publisher.core.electronic_signer import ElectronicSigner


@pytest.fixture
def signer() -> ElectronicSigner:
    return ElectronicSigner()


def test_complex_structure_with_symlinks_and_empty_dirs(signer: ElectronicSigner, tmp_path: Path) -> None:
    """
    Test a complex directory structure:
    - Standard files
    - Empty directories (should be ignored)
    - Symlinks (should be ignored)
    - Nested structures
    """
    # Create structure
    root = tmp_path / "complex_root"
    root.mkdir()

    # 1. Standard files
    (root / "alpha.txt").write_text("alpha")
    (root / "omega.txt").write_text("omega")

    # 2. Empty directory
    (root / "empty_dir").mkdir()

    # 3. Nested structure
    nested = root / "nested" / "deep"
    nested.mkdir(parents=True)
    (nested / "deep_file.txt").write_text("deep")

    # 4. Symlinks
    # Note: Symlinks might not be supported on all test environments (e.g. Windows without admin)
    # If os.symlink fails, we skip that part of the test or log it.
    try:
        # Link to internal file
        (root / "link_internal.txt").symlink_to(root / "alpha.txt")
        # Link to directory
        (root / "link_dir").symlink_to(root / "nested")
    except OSError:
        pytest.skip("Symlinks not supported in this environment")

    # Calculate hash
    hash1 = signer.calculate_bundle_hash(root)

    # ACTION: Remove the empty directory
    (root / "empty_dir").rmdir()
    hash2 = signer.calculate_bundle_hash(root)

    # EXPECTATION: Empty directory removal should NOT change hash
    assert hash1 == hash2

    # ACTION: Modify the symlink (if it exists)
    if (root / "link_internal.txt").exists():
        (root / "link_internal.txt").unlink()
        (root / "link_internal.txt").symlink_to(root / "omega.txt")
        hash3 = signer.calculate_bundle_hash(root)

        # EXPECTATION: Changing symlink target should NOT change hash (since symlinks are ignored)
        assert hash1 == hash3


def test_special_characters_in_filenames(signer: ElectronicSigner, tmp_path: Path) -> None:
    """Test filenames with special characters to ensure encoding robustness."""
    root = tmp_path / "special_root"
    root.mkdir()

    # Unicode characters
    (root / "café.txt").write_text("coffee")

    # Spaces
    (root / "file with spaces.txt").write_text("spaces")

    # Brackets and symbols
    (root / "[config] #1.json").write_text("{}")

    # Calculate hash
    hash_val = signer.calculate_bundle_hash(root)
    assert hash_val is not None
    assert len(hash_val) == 64  # SHA-256 hex length


def test_deeply_nested_git_exclusion(signer: ElectronicSigner, tmp_path: Path) -> None:
    """Test that .git directories are ignored even when deeply nested."""
    root = tmp_path / "git_test"
    root.mkdir()

    (root / "file1.txt").write_text("content")

    # Calculate baseline
    baseline_hash = signer.calculate_bundle_hash(root)

    # Add deeply nested .git
    deep_git = root / "lib" / "modules" / "submodule" / ".git"
    deep_git.mkdir(parents=True)
    (deep_git / "HEAD").write_text("ref: refs/heads/main")

    # Add valid file alongside .git
    (root / "lib" / "modules" / "submodule" / "valid_code.py").write_text("print('hello')")

    # Calculate new hash
    new_hash = signer.calculate_bundle_hash(root)

    # The hash MUST change because we added 'valid_code.py', but NOT because of .git
    assert new_hash != baseline_hash

    # Create another dir with JUST the same valid file, no .git
    root2 = tmp_path / "git_test_clean"
    root2.mkdir()
    (root2 / "file1.txt").write_text("content")
    deep_clean = root2 / "lib" / "modules" / "submodule"
    deep_clean.mkdir(parents=True)
    (deep_clean / "valid_code.py").write_text("print('hello')")

    clean_hash = signer.calculate_bundle_hash(root2)

    # The hash with nested .git should equal the hash of the clean directory structure
    assert new_hash == clean_hash


def test_large_file_simulation(signer: ElectronicSigner, tmp_path: Path) -> None:
    """
    Test hashing a larger file to ensure chunked reading works.
    We won't create a 100MB file to avoid slowing down tests, but 1MB is enough to trigger loops.
    """
    root = tmp_path / "large_file_test"
    root.mkdir()

    large_file = root / "large.bin"
    # Write 1MB of random data
    large_file.write_bytes(os.urandom(1024 * 1024))

    hash_val = signer.calculate_bundle_hash(root)
    assert len(hash_val) == 64

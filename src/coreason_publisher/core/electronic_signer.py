# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_publisher

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from coreason_publisher.utils.logger import logger


class ElectronicSigner:
    """
    The GxP Lock. Implements 21 CFR Part 11 Compliance features.
    Handles cryptographic hashing of artifacts and generating audit trails.
    """

    def __init__(self) -> None:
        pass

    def calculate_bundle_hash(self, bundle_path: Path) -> str:
        """
        Calculates a deterministic SHA-256 hash of the entire directory content.
        Excludes .git directory and other non-essential files.
        """
        if not bundle_path.exists():
            raise FileNotFoundError(f"Bundle path {bundle_path} does not exist")

        sha256_hash = hashlib.sha256()

        # Collect all files to hash
        files_to_hash: List[Path] = []

        for file_path in bundle_path.rglob("*"):
            if not file_path.is_file() or file_path.is_symlink():
                continue

            # Exclude .git directory
            # We check if '.git' is anywhere in the parts relative to bundle_path
            # But rglob comes from bundle_path, so we check parts relative to it?
            # Actually easier to check absolute parts or relative parts.
            rel_path = file_path.relative_to(bundle_path)
            if ".git" in rel_path.parts:
                continue

            # Additional standard exclusions?
            # The requirement says "The 'Thick' Artifact... exact Prompts, Code, Test Data, and Model Weights"
            # So we should be very inclusive. Only skipping .git is safe.

            files_to_hash.append(file_path)

        # Sort strictly by relative path string to ensure determinism
        files_to_hash.sort(key=lambda p: str(p.relative_to(bundle_path)))

        logger.info(f"Hashing {len(files_to_hash)} files in {bundle_path}")

        for file_path in files_to_hash:
            rel_path_str = str(file_path.relative_to(bundle_path)).replace("\\", "/")  # Normalize to forward slash

            # Update hash with filename first to detect renames
            sha256_hash.update(rel_path_str.encode("utf-8"))

            # Update hash with file content
            try:
                # Read in chunks for memory efficiency
                with open(file_path, "rb") as f:
                    for byte_block in iter(lambda: f.read(4096), b""):
                        sha256_hash.update(byte_block)
            except OSError as e:
                logger.error(f"Failed to read file {file_path} for hashing: {e}")
                raise RuntimeError(f"Failed to read file {file_path} for hashing: {e}") from e

        final_hash = sha256_hash.hexdigest()
        logger.debug(f"Bundle hash: {final_hash}")
        return final_hash

    def create_signature(self, bundle_path: Path, user_id: str) -> str:
        """
        Creates a 'signature' for the bundle.
        In this iteration, it returns the bundle hash.
        Future iterations will perform cryptographic signing.
        """
        logger.info(f"Creating signature for {bundle_path} by {user_id}")
        return self.calculate_bundle_hash(bundle_path)

    def verify_signature(self, bundle_path: Path, signature: str) -> bool:
        """
        Verifies that the bundle matches the signature.
        """
        current_hash = self.calculate_bundle_hash(bundle_path)
        is_valid = current_hash == signature

        if is_valid:
            logger.info("Signature verification PASSED")
        else:
            logger.warning(f"Signature verification FAILED. Expected {signature}, got {current_hash}")

        return is_valid

    def format_commit_message(self, original_message: str, user_id: str, signature: str, signer_role: str) -> str:
        """
        Injects the audit trail into the Git commit message.
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        audit_trail = {
            "signer_id": user_id,
            "signer_role": signer_role,
            "signature": signature,
            "timestamp": timestamp,
            "compliance": "21 CFR Part 11",
        }

        # Serialize to JSON string for the block
        audit_block = json.dumps(audit_trail, indent=2)

        formatted_message = (
            f"{original_message}\n\n--- COREASON AUDIT TRAIL ---\n{audit_block}\n----------------------------"
        )
        return formatted_message

    def send_audit_to_veritas(self, user_id: str, signature: str, signer_role: str) -> None:
        """
        Stub for sending audit data to Coreason Veritas.
        """
        # TODO: Implement actual API client
        logger.info(f"[VERITAS STUB] Sent audit: User={user_id}, Role={signer_role}, Sig={signature}")

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
from typing import Any, Dict

from coreason_publisher.utils.logger import logger


class CouncilSnapshot:
    """Handles the creation of the Council Snapshot manifest."""

    def create_snapshot(self, assay_report_path: Path, output_path: Path) -> None:
        """
        Generates the council manifest lock file from the assay report.

        Args:
            assay_report_path: Path to the input assay_report.json.
            output_path: Path to the output council_manifest.lock.

        Raises:
            FileNotFoundError: If the assay report does not exist.
            ValueError: If the assay report is invalid or missing the 'council' key.
        """
        logger.info(f"Generating council snapshot from {assay_report_path} to {output_path}")

        if not assay_report_path.exists():
            logger.error(f"Assay report not found at {assay_report_path}")
            raise FileNotFoundError(f"Assay report not found at {assay_report_path}")

        try:
            with open(assay_report_path, "r", encoding="utf-8") as f:
                data: Dict[str, Any] = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse assay report: {e}")
            raise ValueError(f"Failed to parse assay report: {e}") from e

        if "council" not in data:
            logger.error("Assay report missing 'council' section")
            raise ValueError("Assay report missing 'council' section")

        council_data = data["council"]

        if not isinstance(council_data, dict):
            logger.error(f"Assay report 'council' section must be a dictionary, got {type(council_data).__name__}")
            raise ValueError(f"Assay report 'council' section must be a dictionary, got {type(council_data).__name__}")

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(council_data, f, indent=2, sort_keys=True)
                # Ensure newline at end of file
                f.write("\n")
            logger.info("Council snapshot generated successfully")
        except OSError as e:
            logger.error(f"Failed to write snapshot to {output_path}: {e}")
            raise RuntimeError(f"Failed to write snapshot to {output_path}: {e}") from e

# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_publisher

import importlib.resources
from datetime import datetime, timezone
from typing import Any, Dict

from jinja2 import Template

from coreason_publisher.utils.logger import logger


class CertificateGenerator:
    """Generates the Certificate of Analysis (CoA) from assay reports."""

    TEMPLATE_PACKAGE = "coreason_publisher.templates"
    TEMPLATE_NAME = "certificate.md.j2"

    def generate(self, report_data: Dict[str, Any]) -> str:
        """
        Generates the CoA markdown content.

        Args:
            report_data: The dictionary containing the assay report data.
                         Expected structure:
                         {
                             "council": {"proposer": "...", "judge": "..."},
                             "results": {"pass": bool, "score": float}
                         }

        Returns:
            The rendered markdown string.

        Raises:
            ValueError: If report data is invalid.
            RuntimeError: If template cannot be loaded or rendering fails.
        """
        logger.info("Generating Certificate of Analysis...")

        self._validate_report_data(report_data)

        try:
            template_content = self._load_template()
            template = Template(template_content)
        except Exception as e:
            logger.error(f"Failed to load template: {e}")
            raise RuntimeError(f"Failed to load template: {e}") from e

        try:
            # Prepare context
            context = {
                "status": "PASSED" if report_data["results"]["pass"] else "FAILED",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "council": report_data["council"],
                "results": report_data["results"],
            }
            # Cast to str because jinja2 Template.render might return Any or be untyped in some stubs
            rendered: str = template.render(context)
            logger.info("Certificate generated successfully")
            return rendered
        except Exception as e:
            logger.error(f"Failed to render template: {e}")
            raise RuntimeError(f"Failed to render template: {e}") from e

    def _validate_report_data(self, data: Dict[str, Any]) -> None:
        """Validates the input report data."""
        if "council" not in data:
            raise ValueError("Missing 'council' in report data")
        if "results" not in data:
            raise ValueError("Missing 'results' in report data")
        if "pass" not in data["results"]:
            raise ValueError("Missing 'pass' in results")
        if "score" not in data["results"]:
            raise ValueError("Missing 'score' in results")

    def _load_template(self) -> str:
        """Loads the jinja2 template from the package resources."""
        # Use files() for python 3.9+ compatibility (we are 3.12)
        ref = importlib.resources.files(self.TEMPLATE_PACKAGE) / self.TEMPLATE_NAME
        return ref.read_text(encoding="utf-8")

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
from typing import Any, Dict


class AssayClient(ABC):
    """Abstract base class for interacting with the CoReason Assay service."""

    @abstractmethod
    def get_latest_report(self, project_id: str) -> Dict[str, Any]:
        """
        Retrieves the latest passing assay report for the given project.

        Args:
            project_id: The ID of the project to retrieve the report for.

        Returns:
            The assay report as a dictionary.

        Raises:
            RuntimeError: If the report cannot be retrieved or is invalid.
        """
        pass  # pragma: no cover

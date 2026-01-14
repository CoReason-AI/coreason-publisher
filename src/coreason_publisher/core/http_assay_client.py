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
import os
import urllib.parse
from typing import Any, Dict

import httpx
from coreason_publisher.core.assay_client import AssayClient
from coreason_publisher.utils.logger import logger


class HttpAssayClient(AssayClient):
    """HTTP-based implementation of the AssayClient."""

    def __init__(self, base_url: str | None = None, token: str | None = None):
        """
        Initialize the HttpAssayClient.

        Args:
            base_url: The base URL of the Assay service. Defaults to ASSAY_API_URL env var.
            token: The API token for authentication. Defaults to ASSAY_API_TOKEN env var.
        """
        self.base_url = base_url or os.getenv("ASSAY_API_URL")
        self.token = token or os.getenv("ASSAY_API_TOKEN")

        if not self.base_url:
            logger.error("ASSAY_API_URL not set")
            raise ValueError("ASSAY_API_URL environment variable not set")

        if not self.token:
            logger.error("ASSAY_API_TOKEN not set")
            raise ValueError("ASSAY_API_TOKEN environment variable not set")

        # Normalize base_url to not have a trailing slash for easier concatenation
        self.base_url = self.base_url.rstrip("/")

    def get_latest_report(self, project_id: str) -> Dict[str, Any]:
        """
        Retrieves the latest passing assay report for the given project.

        Args:
            project_id: The ID of the project.

        Returns:
            The assay report as a dictionary.

        Raises:
            RuntimeError: If the report cannot be retrieved.
        """
        # Encode the project_id to handle special characters (e.g., slash in "namespace/project")
        encoded_project_id = urllib.parse.quote(project_id, safe="")
        url = f"{self.base_url}/projects/{encoded_project_id}/reports/latest"
        logger.info(f"Fetching latest assay report from {url}")

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }

        try:
            with httpx.Client() as client:
                response = client.get(url, headers=headers, timeout=30.0)
                response.raise_for_status()

                try:
                    data = response.json()
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON response: {response.text[:200]}")
                    raise RuntimeError("Invalid JSON response from server") from e

                if not isinstance(data, dict):
                    logger.error(f"Unexpected response format: expected dict, got {type(data)}")
                    raise RuntimeError(f"Unexpected response format: expected dict, got {type(data).__name__}")

                logger.info("Successfully retrieved assay report")
                return data

        except httpx.TimeoutException as e:
            logger.error(f"Timeout retrieving report: {e}")
            raise RuntimeError("Timeout retrieving assay report") from e
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error retrieving report: {e.response.status_code} - {e.response.text}")
            raise RuntimeError(f"Failed to retrieve assay report: {e.response.status_code}") from e
        except httpx.RequestError as e:
            logger.error(f"Network error retrieving report: {e}")
            raise RuntimeError(f"Network error retrieving report: {e}") from e
        except Exception as e:
            # Re-raise RuntimeErrors we created above to avoid wrapping them again in the catch-all
            if isinstance(e, RuntimeError):
                raise
            logger.error(f"Unexpected error retrieving report: {e}")
            raise RuntimeError(f"Unexpected error retrieving report: {e}") from e

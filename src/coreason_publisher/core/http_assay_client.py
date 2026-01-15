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
import urllib.parse
from typing import Any, Dict

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from coreason_publisher.config import PublisherConfig
from coreason_publisher.core.assay_client import AssayClient
from coreason_publisher.utils.logger import logger


class HttpAssayClient(AssayClient):
    """HTTP-based implementation of the AssayClient."""

    def __init__(self, config: PublisherConfig):
        """
        Initialize the HttpAssayClient.

        Args:
            config: The publisher configuration object.
        """
        self.config = config

        if not self.config.assay_api_url:
            logger.error("ASSAY_API_URL not set in config")
            raise ValueError("ASSAY_API_URL not set in config")

        if not self.config.assay_api_token:
            logger.error("ASSAY_API_TOKEN not set in config")
            raise ValueError("ASSAY_API_TOKEN not set in config")

        # Normalize base_url to not have a trailing slash for easier concatenation
        self.base_url = self.config.assay_api_url.rstrip("/")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException, httpx.HTTPStatusError)),
        reraise=True
    )
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
            "Authorization": f"Bearer {self.config.assay_api_token.get_secret_value()}",
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

        except httpx.HTTPStatusError as e:
            # Don't retry on 4xx errors (except maybe 429 which we aren't explicitly checking for yet, but let's assume standard behavior)
            # Actually, retry_if_exception_type(httpx.HTTPStatusError) will retry ALL status errors.
            # We probably want to exclude 400, 401, 403, 404 from retry.
            if 400 <= e.response.status_code < 500:
                logger.error(f"Client error retrieving report: {e.response.status_code} - {e.response.text}")
                # We can re-raise a different exception or let it bubble up.
                # If we raise a RuntimeError here, it won't be caught by the retry logic if we configure it right,
                # but currently retry catches HTTPStatusError.
                # Let's just raise RuntimeError which is NOT in the retry list (Wait, it is not?)
                # Ah, I added `retry_if_exception_type` with `httpx.HTTPStatusError`.
                # I should refine the retry logic.
                raise RuntimeError(f"Failed to retrieve assay report: {e.response.status_code}") from e
            raise # Let retry handle 5xx
        except (httpx.RequestError, httpx.TimeoutException) as e:
            logger.warning(f"Network/Timeout error retrieving report: {e}. Retrying...")
            raise
        except Exception as e:
            # Re-raise RuntimeErrors we created above to avoid wrapping them again in the catch-all
            if isinstance(e, RuntimeError):
                raise
            logger.error(f"Unexpected error retrieving report: {e}")
            raise RuntimeError(f"Unexpected error retrieving report: {e}") from e

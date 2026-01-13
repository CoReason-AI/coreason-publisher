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
from typing import Any

import httpx

from coreason_publisher.core.foundry_client import FoundryClient
from coreason_publisher.utils.logger import logger


class HttpFoundryClient(FoundryClient):
    """HTTP-based implementation of the FoundryClient."""

    def __init__(self, base_url: str | None = None, token: str | None = None):
        """
        Initialize the HttpFoundryClient.

        Args:
            base_url: The base URL of the Foundry service. Defaults to FOUNDRY_API_URL env var.
            token: The API token for authentication. Defaults to FOUNDRY_API_TOKEN env var.
        """
        self.base_url = base_url or os.getenv("FOUNDRY_API_URL")
        self.token = token or os.getenv("FOUNDRY_API_TOKEN")

        if not self.base_url:
            logger.error("FOUNDRY_API_URL not set")
            raise ValueError("FOUNDRY_API_URL environment variable not set")

        if not self.token:
            logger.error("FOUNDRY_API_TOKEN not set")
            raise ValueError("FOUNDRY_API_TOKEN environment variable not set")

        # Normalize base_url to not have a trailing slash for easier concatenation
        self.base_url = self.base_url.rstrip("/")

    def submit_for_review(self, draft_id: str, type: str) -> None:
        """Submits a draft for review."""
        encoded_draft_id = urllib.parse.quote(draft_id, safe="")
        url = f"{self.base_url}/drafts/{encoded_draft_id}/submit"
        logger.info(f"Submitting draft {draft_id} for review (type={type})")

        payload = {"type": type}
        self._post(url, payload)

    def approve_release(self, mr_id: int, signature: str) -> None:
        """Approves a release."""
        # mr_id is usually part of the endpoint path or body.
        # PRD says: "Needs approve_release(mr_id, signature) endpoint."
        # Assuming URL structure based on function signature.
        # Could be /releases/{mr_id}/approve or /merge-requests/{mr_id}/approve
        # or /approvals with body.
        # Given "approve_release", let's assume it relates to a release or MR resource.
        # Let's assume POST /merge-requests/{mr_id}/approve

        url = f"{self.base_url}/merge-requests/{mr_id}/approve"
        logger.info(f"Approving release for MR {mr_id}")

        payload = {"signature": signature}
        self._post(url, payload)

    def reject_release(self, draft_id: str, reason: str) -> None:
        """Rejects a release draft."""
        encoded_draft_id = urllib.parse.quote(draft_id, safe="")
        # Assuming URL structure /drafts/{draft_id}/reject
        url = f"{self.base_url}/drafts/{encoded_draft_id}/reject"
        logger.info(f"Rejecting draft {draft_id} with reason: {reason}")

        payload = {"reason": reason}
        self._post(url, payload)

    def get_draft_status(self, draft_id: str) -> str:
        """Retrieves the status of a draft."""
        encoded_draft_id = urllib.parse.quote(draft_id, safe="")
        url = f"{self.base_url}/drafts/{encoded_draft_id}"
        logger.info(f"Fetching status for draft {draft_id}")

        headers = self._get_headers()
        try:
            with httpx.Client() as client:
                response = client.get(url, headers=headers, timeout=30.0)
                response.raise_for_status()
                data = self._parse_json(response)

                if "status" not in data:
                    logger.error(f"Response missing 'status' field: {data}")
                    raise RuntimeError("Response missing 'status' field")

                status = str(data["status"])
                logger.info(f"Draft {draft_id} status: {status}")
                return status

        except httpx.HTTPError as e:
            self._handle_http_error(e)
            raise  # pragma: no cover
        except Exception as e:
            # Re-raise RuntimeErrors we created
            if isinstance(e, RuntimeError):
                raise
            logger.error(f"Unexpected error retrieving draft status: {e}")
            raise RuntimeError(f"Unexpected error retrieving draft status: {e}") from e

    def _post(self, url: str, payload: dict[str, Any]) -> None:
        """Helper to send POST requests."""
        headers = self._get_headers()
        try:
            with httpx.Client() as client:
                response = client.post(url, json=payload, headers=headers, timeout=30.0)
                response.raise_for_status()
                logger.info("Request successful")
        except httpx.HTTPError as e:
            self._handle_http_error(e)
        except Exception as e:
            logger.error(f"Unexpected error during POST to {url}: {e}")
            raise RuntimeError(f"Unexpected error during POST to {url}: {e}") from e

    def _get_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _parse_json(self, response: httpx.Response) -> dict[str, Any]:
        try:
            data = response.json()
            if not isinstance(data, dict):
                logger.error(f"Unexpected response format: expected dict, got {type(data)}")
                raise RuntimeError(f"Unexpected response format: expected dict, got {type(data).__name__}")
            return data
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response: {response.text[:200]}")
            raise RuntimeError("Invalid JSON response from server") from e

    def _handle_http_error(self, e: httpx.HTTPError) -> None:
        if isinstance(e, httpx.TimeoutException):
            logger.error(f"Timeout error: {e}")
            raise RuntimeError("Timeout error during Foundry API call") from e
        if isinstance(e, httpx.HTTPStatusError):
            logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
            raise RuntimeError(f"Foundry API error: {e.response.status_code}") from e
        logger.error(f"Network error: {e}")
        raise RuntimeError(f"Network error during Foundry API call: {e}") from e

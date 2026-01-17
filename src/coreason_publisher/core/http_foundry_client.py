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
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from coreason_publisher.config import PublisherConfig
from coreason_publisher.core.foundry_client import FoundryClient
from coreason_publisher.utils.logger import logger


class HttpFoundryClient(FoundryClient):
    """HTTP-based implementation of the FoundryClient."""

    def __init__(self, config: PublisherConfig):
        """
        Initialize the HttpFoundryClient.

        Args:
            config: The publisher configuration object.
        """
        self.config = config

        if not self.config.foundry_api_url:
            logger.error("FOUNDRY_API_URL not set")
            raise ValueError("FOUNDRY_API_URL not set in config")

        if not self.config.foundry_api_token:
            logger.error("FOUNDRY_API_TOKEN not set")
            raise ValueError("FOUNDRY_API_TOKEN not set in config")

        # Normalize base_url to not have a trailing slash for easier concatenation
        self.base_url = self.config.foundry_api_url.rstrip("/")

    @retry(  # type: ignore[misc]
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException, httpx.HTTPStatusError)),
        reraise=True,
    )
    def submit_for_review(self, draft_id: str, type: str) -> None:
        """Submits a draft for review."""
        encoded_draft_id = urllib.parse.quote(draft_id, safe="")
        url = f"{self.base_url}/drafts/{encoded_draft_id}/submit"
        logger.info(f"Submitting draft {draft_id} for review (type={type})")

        payload = {"type": type}
        self._post(url, payload)

    @retry(  # type: ignore[misc]
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException, httpx.HTTPStatusError)),
        reraise=True,
    )
    def approve_release(self, mr_id: int, signature: str) -> None:
        """Approves a release."""
        url = f"{self.base_url}/merge-requests/{mr_id}/approve"
        logger.info(f"Approving release for MR {mr_id}")

        payload = {"signature": signature}
        self._post(url, payload)

    @retry(  # type: ignore[misc]
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException, httpx.HTTPStatusError)),
        reraise=True,
    )
    def reject_release(self, draft_id: str, reason: str) -> None:
        """Rejects a release draft."""
        encoded_draft_id = urllib.parse.quote(draft_id, safe="")
        url = f"{self.base_url}/drafts/{encoded_draft_id}/reject"
        logger.info(f"Rejecting draft {draft_id} with reason: {reason}")

        payload = {"reason": reason}
        self._post(url, payload)

    @retry(  # type: ignore[misc]
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException, httpx.HTTPStatusError)),
        reraise=True,
    )
    def get_draft_status(self, draft_id: str) -> str:
        """Retrieves the status of a draft."""
        encoded_draft_id = urllib.parse.quote(draft_id, safe="")
        url = f"{self.base_url}/drafts/{encoded_draft_id}"
        logger.info(f"Fetching status for draft {draft_id}")

        headers = self._get_headers()
        try:
            with httpx.Client() as client:
                response = client.get(url, headers=headers, timeout=30.0)

                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as e:
                    self._handle_http_error(e)

                data = self._parse_json(response)

                if "status" not in data:
                    logger.error(f"Response missing 'status' field: {data}")
                    raise RuntimeError("Response missing 'status' field")

                status = str(data["status"])
                logger.info(f"Draft {draft_id} status: {status}")
                return status

        except httpx.HTTPStatusError as e:
            # _handle_http_error might raise RuntimeError which stops retry
            # If it re-raises HTTPStatusError, retry happens.
            # But wait, I call _handle_http_error inside the try block, it raises RuntimeError.
            # RuntimeError is NOT in retry_if_exception_type list. So it won't retry on 4xx.
            # This is correct.
            self._handle_http_error(e)
        except (httpx.RequestError, httpx.TimeoutException) as e:
            logger.warning(f"Network/Timeout error retrieving draft status: {e}. Retrying...")
            raise
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise
            logger.error(f"Unexpected error retrieving draft status: {e}")
            raise RuntimeError(f"Unexpected error retrieving draft status: {e}") from e

        return ""  # pragma: no cover

    def _post(self, url: str, payload: dict[str, Any]) -> None:
        """Helper to send POST requests."""
        headers = self._get_headers()
        try:
            with httpx.Client() as client:
                response = client.post(url, json=payload, headers=headers, timeout=30.0)
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as e:
                    self._handle_http_error(e)
                logger.info("Request successful")
        except httpx.HTTPStatusError as e:
            self._handle_http_error(e)
        except (httpx.RequestError, httpx.TimeoutException) as e:
            logger.warning(f"Network/Timeout error during POST to {url}: {e}. Retrying...")
            raise
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise
            logger.error(f"Unexpected error during POST to {url}: {e}")
            raise RuntimeError(f"Unexpected error during POST to {url}: {e}") from e

    def _get_headers(self) -> dict[str, str]:
        if not self.config.foundry_api_token:
            raise ValueError("FOUNDRY_API_TOKEN missing")  # pragma: no cover

        return {
            "Authorization": f"Bearer {self.config.foundry_api_token.get_secret_value()}",
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

    def _handle_http_error(self, e: httpx.HTTPStatusError) -> None:
        # If client error, raise RuntimeError to stop retries (unless we want to retry some 4xx?)
        # Generally 4xx are permanent errors.
        if 400 <= e.response.status_code < 500:
            logger.error(f"Client error: {e.response.status_code} - {e.response.text}")
            raise RuntimeError(f"Foundry API error: {e.response.status_code}") from e
        # 5xx errors should bubble up as HTTPStatusError to trigger retry
        raise e

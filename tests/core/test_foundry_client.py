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
from unittest.mock import patch

import httpx
import pytest
import respx
from httpx import Response

from coreason_publisher.core.http_foundry_client import HttpFoundryClient


@pytest.fixture  # type: ignore[misc]
def client(monkeypatch: pytest.MonkeyPatch) -> HttpFoundryClient:
    monkeypatch.setenv("FOUNDRY_API_URL", "https://api.foundry.com")
    monkeypatch.setenv("FOUNDRY_API_TOKEN", "test-token")
    return HttpFoundryClient()


@respx.mock  # type: ignore[misc]
def test_submit_for_review_success(client: HttpFoundryClient) -> None:
    draft_id = "draft-123"
    type_ = "minor"

    route = respx.post(f"https://api.foundry.com/drafts/{draft_id}/submit").mock(
        return_value=Response(200, json={"message": "submitted"})
    )

    client.submit_for_review(draft_id, type_)

    assert route.called
    assert route.calls.last.request.headers["Authorization"] == "Bearer test-token"
    # Compare parsed JSON to avoid formatting issues
    assert json.loads(route.calls.last.request.read()) == {"type": "minor"}


@respx.mock  # type: ignore[misc]
def test_submit_for_review_failure(client: HttpFoundryClient) -> None:
    draft_id = "draft-123"

    respx.post(f"https://api.foundry.com/drafts/{draft_id}/submit").mock(
        return_value=Response(500, json={"error": "server error"})
    )

    with pytest.raises(RuntimeError, match="Foundry API error: 500"):
        client.submit_for_review(draft_id, "patch")


@respx.mock  # type: ignore[misc]
def test_approve_release_success(client: HttpFoundryClient) -> None:
    mr_id = 456
    signature = "sig-abc-123"

    route = respx.post(f"https://api.foundry.com/merge-requests/{mr_id}/approve").mock(
        return_value=Response(200, json={"message": "approved"})
    )

    client.approve_release(mr_id, signature)

    assert route.called
    assert route.calls.last.request.headers["Authorization"] == "Bearer test-token"
    assert json.loads(route.calls.last.request.read()) == {"signature": "sig-abc-123"}


@respx.mock  # type: ignore[misc]
def test_approve_release_failure(client: HttpFoundryClient) -> None:
    mr_id = 456

    respx.post(f"https://api.foundry.com/merge-requests/{mr_id}/approve").mock(
        return_value=Response(404, json={"error": "not found"})
    )

    with pytest.raises(RuntimeError, match="Foundry API error: 404"):
        client.approve_release(mr_id, "sig")


@respx.mock  # type: ignore[misc]
def test_get_draft_status_success(client: HttpFoundryClient) -> None:
    draft_id = "draft-789"

    respx.get(f"https://api.foundry.com/drafts/{draft_id}").mock(
        return_value=Response(200, json={"id": draft_id, "status": "PENDING_SRB"})
    )

    status = client.get_draft_status(draft_id)
    assert status == "PENDING_SRB"


@respx.mock  # type: ignore[misc]
def test_get_draft_status_missing_field(client: HttpFoundryClient) -> None:
    draft_id = "draft-789"

    respx.get(f"https://api.foundry.com/drafts/{draft_id}").mock(
        return_value=Response(200, json={"id": draft_id})  # Missing status
    )

    with pytest.raises(RuntimeError, match="Response missing 'status' field"):
        client.get_draft_status(draft_id)


@respx.mock  # type: ignore[misc]
def test_get_draft_status_invalid_json(client: HttpFoundryClient) -> None:
    draft_id = "draft-789"

    respx.get(f"https://api.foundry.com/drafts/{draft_id}").mock(return_value=Response(200, text="not json"))

    with pytest.raises(RuntimeError, match="Invalid JSON response"):
        client.get_draft_status(draft_id)


@respx.mock  # type: ignore[misc]
def test_get_draft_status_not_dict(client: HttpFoundryClient) -> None:
    draft_id = "draft-789"

    respx.get(f"https://api.foundry.com/drafts/{draft_id}").mock(
        return_value=Response(200, json=["list", "not", "dict"])
    )

    with pytest.raises(RuntimeError, match="Unexpected response format: expected dict, got list"):
        client.get_draft_status(draft_id)


@respx.mock  # type: ignore[misc]
def test_get_draft_status_http_error(client: HttpFoundryClient) -> None:
    draft_id = "draft-789"

    respx.get(f"https://api.foundry.com/drafts/{draft_id}").mock(return_value=Response(503, text="Service Unavailable"))

    with pytest.raises(RuntimeError, match="Foundry API error: 503"):
        client.get_draft_status(draft_id)


@respx.mock  # type: ignore[misc]
def test_timeout_error(client: HttpFoundryClient) -> None:
    draft_id = "draft-timeout"

    respx.post(f"https://api.foundry.com/drafts/{draft_id}/submit").mock(side_effect=httpx.TimeoutException("timeout"))

    with pytest.raises(RuntimeError, match="Timeout error during Foundry API call"):
        client.submit_for_review(draft_id, "minor")


@respx.mock  # type: ignore[misc]
def test_network_error(client: HttpFoundryClient) -> None:
    draft_id = "draft-net-error"

    respx.post(f"https://api.foundry.com/drafts/{draft_id}/submit").mock(
        side_effect=httpx.RequestError("connection refused")
    )

    with pytest.raises(RuntimeError, match="Network error during Foundry API call"):
        client.submit_for_review(draft_id, "minor")


def test_missing_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FOUNDRY_API_URL", raising=False)
    monkeypatch.delenv("FOUNDRY_API_TOKEN", raising=False)

    with pytest.raises(ValueError, match="FOUNDRY_API_URL environment variable not set"):
        HttpFoundryClient()

    monkeypatch.setenv("FOUNDRY_API_URL", "http://example.com")
    with pytest.raises(ValueError, match="FOUNDRY_API_TOKEN environment variable not set"):
        HttpFoundryClient()


@respx.mock  # type: ignore[misc]
def test_post_unexpected_exception(client: HttpFoundryClient) -> None:
    # Test unexpected exception in _post, catching generic Exception
    # We can mock httpx.Client to raise something unexpected

    draft_id = "draft-unexpected"
    type_ = "minor"

    with pytest.raises(RuntimeError, match="Unexpected error during POST"):
        with patch("httpx.Client.post", side_effect=Exception("Boom")):
            client.submit_for_review(draft_id, type_)


@respx.mock  # type: ignore[misc]
def test_get_draft_status_unexpected_exception(client: HttpFoundryClient) -> None:
    draft_id = "draft-unexpected"

    with pytest.raises(RuntimeError, match="Unexpected error retrieving draft status"):
        with patch("httpx.Client.get", side_effect=Exception("Boom")):
            client.get_draft_status(draft_id)


@respx.mock  # type: ignore[misc]
def test_get_draft_status_runtime_error_reraise(client: HttpFoundryClient) -> None:
    # Ensure RuntimeErrors raised inside get_draft_status are re-raised without wrapping
    draft_id = "draft-reraise"

    # Simulate _parse_json raising RuntimeError
    respx.get(f"https://api.foundry.com/drafts/{draft_id}").mock(return_value=Response(200, text="not json"))

    with pytest.raises(RuntimeError, match="Invalid JSON response"):
        client.get_draft_status(draft_id)


# --- Edge Cases and Complex Scenarios ---


@respx.mock  # type: ignore[misc]
def test_url_encoding(client: HttpFoundryClient) -> None:
    """Test that draft IDs with special characters are correctly encoded."""
    draft_id = "group/project/draft#1"
    # Expected encoding: group%2Fproject%2Fdraft%231
    expected_path = "/drafts/group%2Fproject%2Fdraft%231/submit"

    route = respx.post(f"https://api.foundry.com{expected_path}").mock(
        return_value=Response(200, json={"message": "ok"})
    )

    client.submit_for_review(draft_id, "minor")

    assert route.called
    # httpx.URL.path returns decoded path. We need to check raw_path to verify encoding.
    # raw_path is bytes.
    assert route.calls.last.request.url.raw_path == expected_path.encode()


def test_malformed_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a malformed base URL raises a proper error when used."""
    monkeypatch.setenv("FOUNDRY_API_URL", "invalid-url-without-scheme")
    monkeypatch.setenv("FOUNDRY_API_TOKEN", "test-token")
    client = HttpFoundryClient()  # Should not raise here

    # httpx raises UnsupportedProtocol for missing scheme
    with pytest.raises(RuntimeError, match="Network error during Foundry API call"):
        client.get_draft_status("123")


@respx.mock  # type: ignore[misc]
def test_status_type_conversion(client: HttpFoundryClient) -> None:
    """Test handling of non-string status values."""
    draft_id = "123"

    # Int status
    respx.get(f"https://api.foundry.com/drafts/{draft_id}").mock(
        return_value=Response(200, json={"id": draft_id, "status": 123})
    )
    assert client.get_draft_status(draft_id) == "123"

    # None status
    respx.get(f"https://api.foundry.com/drafts/{draft_id}").mock(
        return_value=Response(200, json={"id": draft_id, "status": None})
    )
    assert client.get_draft_status(draft_id) == "None"


@respx.mock  # type: ignore[misc]
def test_empty_arguments(client: HttpFoundryClient) -> None:
    """Test calling methods with empty strings."""
    draft_id = ""
    # urllib.parse.quote("") is ""
    # Path becomes /drafts//submit

    respx.post("https://api.foundry.com/drafts//submit").mock(return_value=Response(404, json={"error": "Not Found"}))

    with pytest.raises(RuntimeError, match="Foundry API error: 404"):
        client.submit_for_review(draft_id, "minor")


@respx.mock  # type: ignore[misc]
def test_reject_release(client: HttpFoundryClient) -> None:
    draft_id = "draft-123"
    reason = "Bad code"
    encoded_draft_id = "draft-123"

    route = respx.post(f"https://api.foundry.com/drafts/{encoded_draft_id}/reject").mock(
        return_value=Response(200, json={"status": "rejected"})
    )

    client.reject_release(draft_id, reason)

    # Verify post
    assert route.called
    assert route.call_count == 1
    req = route.calls.last.request
    assert req.method == "POST"
    assert json.loads(req.content) == {"reason": reason}

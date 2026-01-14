# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_publisher

from collections.abc import Generator
from unittest import mock

import httpx
import pytest
import respx

from coreason_publisher.core.http_assay_client import HttpAssayClient


@pytest.fixture  # type: ignore[misc]
def mock_env(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Sets up environment variables for testing."""
    monkeypatch.setenv("ASSAY_API_URL", "https://api.assay.coreason.ai")
    monkeypatch.setenv("ASSAY_API_TOKEN", "test-token")
    yield


def test_init_raises_error_missing_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that __init__ raises ValueError if env vars are missing."""
    monkeypatch.delenv("ASSAY_API_URL", raising=False)
    monkeypatch.delenv("ASSAY_API_TOKEN", raising=False)

    with pytest.raises(ValueError, match="ASSAY_API_URL environment variable not set"):
        HttpAssayClient()

    monkeypatch.setenv("ASSAY_API_URL", "http://test")
    with pytest.raises(ValueError, match="ASSAY_API_TOKEN environment variable not set"):
        HttpAssayClient()


def test_get_latest_report_success(mock_env: None) -> None:
    """Test successful retrieval of assay report."""
    project_id = "test-project"
    expected_data = {"id": "123", "status": "passed"}

    with respx.mock(base_url="https://api.assay.coreason.ai") as respx_mock:
        respx_mock.get(f"/projects/{project_id}/reports/latest").mock(
            return_value=httpx.Response(200, json=expected_data)
        )

        client = HttpAssayClient()
        data = client.get_latest_report(project_id)

        assert data == expected_data


def test_get_latest_report_404(mock_env: None) -> None:
    """Test retrieval when report is not found."""
    project_id = "unknown-project"

    with respx.mock(base_url="https://api.assay.coreason.ai") as respx_mock:
        respx_mock.get(f"/projects/{project_id}/reports/latest").mock(
            return_value=httpx.Response(404, json={"error": "Not Found"})
        )

        client = HttpAssayClient()
        with pytest.raises(RuntimeError, match="Failed to retrieve assay report: 404"):
            client.get_latest_report(project_id)


def test_get_latest_report_500(mock_env: None) -> None:
    """Test retrieval when server errors."""
    project_id = "test-project"

    with respx.mock(base_url="https://api.assay.coreason.ai") as respx_mock:
        respx_mock.get(f"/projects/{project_id}/reports/latest").mock(
            return_value=httpx.Response(500, json={"error": "Server Error"})
        )

        client = HttpAssayClient()
        with pytest.raises(RuntimeError, match="Failed to retrieve assay report: 500"):
            client.get_latest_report(project_id)


def test_get_latest_report_connection_error(mock_env: None) -> None:
    """Test retrieval when connection fails."""
    project_id = "test-project"

    with respx.mock(base_url="https://api.assay.coreason.ai") as respx_mock:
        respx_mock.get(f"/projects/{project_id}/reports/latest").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        client = HttpAssayClient()
        with pytest.raises(RuntimeError, match="Network error retrieving report"):
            client.get_latest_report(project_id)


def test_get_latest_report_unexpected_error(mock_env: None) -> None:
    """Test retrieval when unexpected error occurs."""
    project_id = "test-project"

    # Mock httpx.Client to raise a generic Exception
    with mock.patch("httpx.Client", side_effect=Exception("Boom")):
        client = HttpAssayClient()
        with pytest.raises(RuntimeError, match="Unexpected error retrieving report"):
            client.get_latest_report(project_id)


def test_get_latest_report_timeout(mock_env: None) -> None:
    """Test retrieval when request times out."""
    project_id = "test-project"

    with respx.mock(base_url="https://api.assay.coreason.ai") as respx_mock:
        respx_mock.get(f"/projects/{project_id}/reports/latest").mock(side_effect=httpx.TimeoutException("Timeout"))

        client = HttpAssayClient()
        with pytest.raises(RuntimeError, match="Timeout retrieving assay report"):
            client.get_latest_report(project_id)


def test_get_latest_report_invalid_json(mock_env: None) -> None:
    """Test retrieval when server returns invalid JSON."""
    project_id = "test-project"

    with respx.mock(base_url="https://api.assay.coreason.ai") as respx_mock:
        respx_mock.get(f"/projects/{project_id}/reports/latest").mock(return_value=httpx.Response(200, text="Not JSON"))

        client = HttpAssayClient()
        with pytest.raises(RuntimeError, match="Invalid JSON response from server"):
            client.get_latest_report(project_id)


def test_get_latest_report_non_dict_response(mock_env: None) -> None:
    """Test retrieval when server returns a JSON list instead of a dict."""
    project_id = "test-project"

    with respx.mock(base_url="https://api.assay.coreason.ai") as respx_mock:
        respx_mock.get(f"/projects/{project_id}/reports/latest").mock(
            return_value=httpx.Response(200, json=[{"id": "1"}])
        )

        client = HttpAssayClient()
        with pytest.raises(RuntimeError, match="Unexpected response format: expected dict, got list"):
            client.get_latest_report(project_id)


def test_get_latest_report_url_construction(mock_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test correct URL construction with trailing slashes."""
    project_id = "test-project"

    # Test with trailing slash in env var
    monkeypatch.setenv("ASSAY_API_URL", "https://api.assay.coreason.ai/")

    client = HttpAssayClient()
    # Check internal base_url attribute is stripped
    assert client.base_url == "https://api.assay.coreason.ai"

    with respx.mock(base_url="https://api.assay.coreason.ai") as respx_mock:
        route = respx_mock.get(f"/projects/{project_id}/reports/latest").mock(return_value=httpx.Response(200, json={}))

        client.get_latest_report(project_id)
        assert route.called


def test_get_latest_report_special_chars_project_id(mock_env: None) -> None:
    """Test that project ID is URL-encoded."""
    project_id = "group/subgroup/project"
    encoded_id = "group%2Fsubgroup%2Fproject"

    with respx.mock(base_url="https://api.assay.coreason.ai") as respx_mock:
        # Expect the encoded URL
        route = respx_mock.get(f"/projects/{encoded_id}/reports/latest").mock(return_value=httpx.Response(200, json={}))

        client = HttpAssayClient()
        client.get_latest_report(project_id)
        assert route.called

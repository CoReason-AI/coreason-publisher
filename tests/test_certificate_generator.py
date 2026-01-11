# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_publisher

from typing import Any, Dict
from unittest.mock import patch

import pytest

from coreason_publisher.core.certificate_generator import CertificateGenerator


@pytest.fixture  # type: ignore
def generator() -> CertificateGenerator:
    return CertificateGenerator()


@pytest.fixture  # type: ignore
def valid_report() -> Dict[str, Any]:
    return {
        "council": {"proposer": "gpt-4-0613", "judge": "claude-3-opus-20240229"},
        "results": {"pass": True, "score": 98.5},
    }


def test_generate_success(generator: CertificateGenerator, valid_report: Dict[str, Any]) -> None:
    """Test successful generation of CoA."""
    cert = generator.generate(valid_report)

    assert "# Certificate of Analysis" in cert
    assert "**Status:** PASSED" in cert
    assert "| gpt-4-0613 |" in cert or "| proposer | gpt-4-0613 |" in cert
    assert "| claude-3-opus-20240229 |" in cert or "| judge | claude-3-opus-20240229 |" in cert
    assert "* **Score:** 98.5" in cert
    assert "* **Pass:** True" in cert
    assert "Timestamp" in cert


def test_generate_failed_status(generator: CertificateGenerator, valid_report: Dict[str, Any]) -> None:
    """Test CoA generation for failed validation."""
    valid_report["results"]["pass"] = False
    cert = generator.generate(valid_report)
    assert "**Status:** FAILED" in cert


def test_missing_council(generator: CertificateGenerator) -> None:
    """Test validation error when council is missing."""
    with pytest.raises(ValueError, match="Missing 'council'"):
        generator.generate({"results": {"pass": True, "score": 100}})


def test_missing_results(generator: CertificateGenerator) -> None:
    """Test validation error when results is missing."""
    with pytest.raises(ValueError, match="Missing 'results'"):
        generator.generate({"council": {}})


def test_missing_result_fields(generator: CertificateGenerator) -> None:
    """Test validation error when specific result fields are missing."""
    with pytest.raises(ValueError, match="Missing 'pass'"):
        generator.generate({"council": {}, "results": {"score": 10}})

    with pytest.raises(ValueError, match="Missing 'score'"):
        generator.generate({"council": {}, "results": {"pass": True}})


def test_template_loading(generator: CertificateGenerator) -> None:
    """Test that the template loads correctly."""
    content = generator._load_template()
    assert "{{ status }}" in content
    assert "Council Manifest" in content


def test_load_template_failure(generator: CertificateGenerator, valid_report: Dict[str, Any]) -> None:
    """Test failure during template loading."""
    with patch("importlib.resources.files", side_effect=Exception("Resource error")):
        with pytest.raises(RuntimeError, match="Failed to load template: Resource error"):
            generator.generate(valid_report)


def test_render_template_failure(generator: CertificateGenerator, valid_report: Dict[str, Any]) -> None:
    """Test failure during template rendering."""
    # We can mock Template class or the template object.
    # Since we are not mocking load_template here, it returns a string.
    # The Template constructor is called. We can mock jinja2.Template.
    with patch("coreason_publisher.core.certificate_generator.Template") as mock_template_cls:
        mock_template_instance = mock_template_cls.return_value
        mock_template_instance.render.side_effect = Exception("Render error")

        with pytest.raises(RuntimeError, match="Failed to render template: Render error"):
            generator.generate(valid_report)

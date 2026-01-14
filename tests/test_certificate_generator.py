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


# --- Edge Case & Complex Scenario Tests ---


def test_generate_complex_characters(generator: CertificateGenerator) -> None:
    """Test generation with Unicode and special characters that might break Markdown tables."""
    report = {
        "council": {
            "proposer": "gpt-4 | version-2",  # Contains pipe
            "judge": "claude-3 🤖",  # Contains emoji
            "reviewer": "Dr. O'Neil & Sons",  # Contains special chars
        },
        "results": {"pass": True, "score": 100.0},
    }
    cert = generator.generate(report)

    # Check that content is present
    assert "gpt-4 | version-2" in cert
    assert "claude-3 🤖" in cert
    assert "Dr. O'Neil & Sons" in cert

    # Note: If we don't escape pipes, this test might pass but the Markdown would be broken.
    # We should verify if we want to enforce escaping.
    # For now, let's just ensure it generates without error and contains the string.


def test_generate_large_council(generator: CertificateGenerator) -> None:
    """Test with a large number of council members."""
    council = {f"role_{i}": f"model_{i}" for i in range(50)}
    report = {"council": council, "results": {"pass": True, "score": 99.9}}
    cert = generator.generate(report)

    assert "| role_0 | model_0 |" in cert
    assert "| role_49 | model_49 |" in cert


def test_generate_boundary_scores(generator: CertificateGenerator) -> None:
    """Test with boundary score values."""
    report_zero = {"council": {"a": "b"}, "results": {"pass": False, "score": 0.0}}
    cert_zero = generator.generate(report_zero)
    assert "**Score:** 0.0" in cert_zero

    report_neg = {"council": {"a": "b"}, "results": {"pass": False, "score": -1.5}}
    cert_neg = generator.generate(report_neg)
    assert "**Score:** -1.5" in cert_neg


def test_generate_extra_fields(generator: CertificateGenerator, valid_report: Dict[str, Any]) -> None:
    """Test with extra ignored fields in the input."""
    valid_report["extra_field"] = "ignore me"
    valid_report["council"]["extra_role_data"] = {"meta": "data"}  # This might be rendered as string

    cert = generator.generate(valid_report)
    assert "PASSED" in cert
    # extra_role_data is in council dict, so it will be iterated.
    # It will render as key: extra_role_data, value: {'meta': 'data'}
    assert "| extra_role_data | {'meta': 'data'} |" in cert

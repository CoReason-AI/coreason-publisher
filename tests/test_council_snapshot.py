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
from pathlib import Path

import pytest
from coreason_publisher.core.council_snapshot import CouncilSnapshot


def test_create_snapshot_success(tmp_path: Path) -> None:
    """Test successful generation of council snapshot."""
    report_path = tmp_path / "assay_report.json"
    output_path = tmp_path / "council_manifest.lock"

    report_data = {
        "council": {"proposer": "gpt-4-0613", "judge": "claude-3-opus"},
        "results": {"pass": True, "score": 98.5},
    }
    report_path.write_text(json.dumps(report_data))

    snapshot = CouncilSnapshot()
    snapshot.create_snapshot(report_path, output_path)

    assert output_path.exists()
    content = json.loads(output_path.read_text())
    assert content == report_data["council"]


def test_create_snapshot_missing_file(tmp_path: Path) -> None:
    """Test error when assay report is missing."""
    report_path = tmp_path / "non_existent.json"
    output_path = tmp_path / "council_manifest.lock"

    snapshot = CouncilSnapshot()
    with pytest.raises(FileNotFoundError, match="Assay report not found"):
        snapshot.create_snapshot(report_path, output_path)


def test_create_snapshot_invalid_json(tmp_path: Path) -> None:
    """Test error when assay report is not valid JSON."""
    report_path = tmp_path / "assay_report.json"
    output_path = tmp_path / "council_manifest.lock"
    report_path.write_text("invalid json content")

    snapshot = CouncilSnapshot()
    with pytest.raises(ValueError, match="Failed to parse assay report"):
        snapshot.create_snapshot(report_path, output_path)


def test_create_snapshot_missing_council_key(tmp_path: Path) -> None:
    """Test error when assay report is missing 'council' key."""
    report_path = tmp_path / "assay_report.json"
    output_path = tmp_path / "council_manifest.lock"
    report_data = {"results": {"pass": True}}
    report_path.write_text(json.dumps(report_data))

    snapshot = CouncilSnapshot()
    with pytest.raises(ValueError, match="Assay report missing 'council' section"):
        snapshot.create_snapshot(report_path, output_path)


def test_create_snapshot_write_error(tmp_path: Path) -> None:
    """Test handling of write errors."""
    report_path = tmp_path / "assay_report.json"
    # Try to write to a directory path, which should fail
    output_path = tmp_path / "output_dir"
    output_path.mkdir()

    report_data = {"council": {"key": "value"}}
    report_path.write_text(json.dumps(report_data))

    snapshot = CouncilSnapshot()
    with pytest.raises(RuntimeError, match="Failed to write snapshot"):
        snapshot.create_snapshot(report_path, output_path)


def test_create_snapshot_council_not_dict(tmp_path: Path) -> None:
    """Test error when 'council' section is not a dictionary."""
    report_path = tmp_path / "assay_report.json"
    output_path = tmp_path / "council_manifest.lock"

    # 'council' is a list, which should fail validation
    report_data = {"council": ["model-a", "model-b"], "results": {"pass": True}}
    report_path.write_text(json.dumps(report_data))

    snapshot = CouncilSnapshot()
    with pytest.raises(ValueError, match="Assay report 'council' section must be a dictionary"):
        snapshot.create_snapshot(report_path, output_path)


def test_create_snapshot_unicode_support(tmp_path: Path) -> None:
    """Test that Unicode characters (e.g., emojis, non-ASCII) are preserved."""
    report_path = tmp_path / "assay_report.json"
    output_path = tmp_path / "council_manifest.lock"

    report_data = {"council": {"proposer": "gpt-4-🚀", "judge": "Mölln-7B"}, "results": {"pass": True}}
    report_path.write_text(json.dumps(report_data, ensure_ascii=False), encoding="utf-8")

    snapshot = CouncilSnapshot()
    snapshot.create_snapshot(report_path, output_path)

    assert output_path.exists()
    content = json.loads(output_path.read_text(encoding="utf-8"))
    assert content["proposer"] == "gpt-4-🚀"
    assert content["judge"] == "Mölln-7B"


def test_create_snapshot_complex_nested_structure(tmp_path: Path) -> None:
    """Test that deep nested structures within the council object are handled correctly."""
    report_path = tmp_path / "assay_report.json"
    output_path = tmp_path / "council_manifest.lock"

    council_structure = {
        "primary_judge": {"name": "claude-3", "parameters": {"temperature": 0.1, "top_p": 0.9}},
        "jury": [{"name": "gpt-3.5", "role": "critic"}, {"name": "llama-3", "role": "advocate"}],
    }

    report_data = {"council": council_structure, "results": {"pass": True}}
    report_path.write_text(json.dumps(report_data))

    snapshot = CouncilSnapshot()
    snapshot.create_snapshot(report_path, output_path)

    content = json.loads(output_path.read_text())
    assert content == council_structure


def test_create_snapshot_large_irrelevant_data(tmp_path: Path) -> None:
    """
    Test that large amounts of irrelevant data in other fields
    do not affect the extraction of the council section.
    """
    report_path = tmp_path / "assay_report.json"
    output_path = tmp_path / "council_manifest.lock"

    # Generate a large list of dummy data
    large_data = ["x" * 1000 for _ in range(1000)]  # ~1MB of data

    report_data = {"council": {"proposer": "fast-model"}, "results": {"pass": True, "logs": large_data}}
    report_path.write_text(json.dumps(report_data))

    snapshot = CouncilSnapshot()
    snapshot.create_snapshot(report_path, output_path)

    content = json.loads(output_path.read_text())
    assert content == {"proposer": "fast-model"}

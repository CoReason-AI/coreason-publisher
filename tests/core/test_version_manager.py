# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_publisher

from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest

from coreason_publisher.core.git_provider import GitProvider
from coreason_publisher.core.version_manager import BumpType, VersionManager


@pytest.fixture  # type: ignore[misc]
def mock_git_provider() -> Generator[MagicMock, None, None]:
    yield MagicMock(spec=GitProvider)


@pytest.fixture  # type: ignore[misc]
def version_manager(mock_git_provider: MagicMock) -> Generator[VersionManager, None, None]:
    yield VersionManager(mock_git_provider)


class TestVersionManager:
    def test_calculate_next_version_initial(self, version_manager: VersionManager) -> None:
        """Test calculation when no previous version exists."""
        assert version_manager.calculate_next_version(None, BumpType.MINOR) == "v0.1.0"
        assert version_manager.calculate_next_version(None, BumpType.MAJOR) == "v0.1.0"
        assert version_manager.calculate_next_version(None, BumpType.PATCH) == "v0.1.0"
        # Empty string should also default
        assert version_manager.calculate_next_version("", BumpType.PATCH) == "v0.1.0"

    def test_calculate_next_version_patch(self, version_manager: VersionManager) -> None:
        assert version_manager.calculate_next_version("v1.0.0", BumpType.PATCH) == "v1.0.1"
        assert version_manager.calculate_next_version("1.0.0", BumpType.PATCH) == "v1.0.1"

    def test_calculate_next_version_minor(self, version_manager: VersionManager) -> None:
        assert version_manager.calculate_next_version("v1.0.5", BumpType.MINOR) == "v1.1.0"
        assert version_manager.calculate_next_version("0.1.0", BumpType.MINOR) == "v0.2.0"

    def test_calculate_next_version_major(self, version_manager: VersionManager) -> None:
        assert version_manager.calculate_next_version("v1.5.9", BumpType.MAJOR) == "v2.0.0"
        assert version_manager.calculate_next_version("0.1.0", BumpType.MAJOR) == "v1.0.0"

    def test_calculate_next_version_invalid(self, version_manager: VersionManager) -> None:
        """Test that invalid version formats raise ValueError."""
        invalid_versions = [
            "invalid",
            "v1.0",  # Missing patch
            "1",  # Missing minor/patch
            "v1.0.0-beta",  # Non-integer components (basic implementation limitation)
            "v1.0.a",
        ]
        for v in invalid_versions:
            with pytest.raises(ValueError):
                version_manager.calculate_next_version(v, BumpType.PATCH)

    def test_calculate_next_version_large_numbers(self, version_manager: VersionManager) -> None:
        """Test bumping with large version numbers."""
        assert version_manager.calculate_next_version("v99.99.99", BumpType.PATCH) == "v99.99.100"
        assert version_manager.calculate_next_version("v99.99.99", BumpType.MINOR) == "v99.100.0"
        assert version_manager.calculate_next_version("v99.99.99", BumpType.MAJOR) == "v100.0.0"
        assert version_manager.calculate_next_version("v2023.12.31", BumpType.PATCH) == "v2023.12.32"

    def test_get_current_version_tags(
        self, version_manager: VersionManager, mock_git_provider: MagicMock, tmp_path: Path
    ) -> None:
        """Test getting version from git tags."""
        mock_git_provider.get_last_tag.return_value = "v1.2.3"
        assert version_manager.get_current_version(tmp_path) == "v1.2.3"

    def test_get_current_version_none(
        self, version_manager: VersionManager, mock_git_provider: MagicMock, tmp_path: Path
    ) -> None:
        """Test when no tags exist."""
        mock_git_provider.get_last_tag.return_value = None
        assert version_manager.get_current_version(tmp_path) is None

    def test_get_current_version_mismatch(
        self, version_manager: VersionManager, mock_git_provider: MagicMock, tmp_path: Path
    ) -> None:
        """Test when tags and agent.yaml mismatch."""
        mock_git_provider.get_last_tag.return_value = "v1.2.3"

        # Create agent.yaml with different version
        agent_yaml = tmp_path / "agent.yaml"
        agent_yaml.write_text('version: "1.0.0"', encoding="utf-8")

        # Should warn but return tag version
        assert version_manager.get_current_version(tmp_path) == "v1.2.3"

    def test_read_agent_yaml_exception(self, version_manager: VersionManager, tmp_path: Path) -> None:
        """Test exception handling when reading agent.yaml."""
        agent_yaml = tmp_path / "agent.yaml"
        agent_yaml.touch()

        # Mock Path.read_text to raise exception
        with patch.object(Path, "read_text", side_effect=PermissionError("Boom")):
            assert version_manager._read_agent_yaml_version(tmp_path) is None

    def test_update_files_create_new(self, version_manager: VersionManager, tmp_path: Path) -> None:
        """Test creating new files if they don't exist."""
        version_manager.update_files(tmp_path, "v1.0.0")

        agent_yaml = tmp_path / "agent.yaml"
        assert agent_yaml.exists()
        assert 'version: "1.0.0"' in agent_yaml.read_text()

        changelog = tmp_path / "CHANGELOG.md"
        assert changelog.exists()
        assert "## [1.0.0] -" in changelog.read_text()

    def test_update_files_existing(self, version_manager: VersionManager, tmp_path: Path) -> None:
        """Test updating existing files."""
        # Setup existing files
        agent_yaml = tmp_path / "agent.yaml"
        agent_yaml.write_text('name: test\nversion: "0.1.0"\nother: val', encoding="utf-8")

        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text("# Changelog\n\n## [0.1.0] - 2024-01-01\n\n- Old changes", encoding="utf-8")

        version_manager.update_files(tmp_path, "v0.2.0")

        # Check agent.yaml
        yaml_content = agent_yaml.read_text()
        assert 'version: "0.2.0"' in yaml_content
        assert "name: test" in yaml_content  # Preserves other content

        # Check CHANGELOG.md
        changelog_content = changelog.read_text()
        assert "## [0.2.0] -" in changelog_content
        assert "## [0.1.0] -" in changelog_content
        # Ensure new version is before old version
        assert changelog_content.find("## [0.2.0]") < changelog_content.find("## [0.1.0]")

    def test_update_agent_yaml_quotes(self, version_manager: VersionManager, tmp_path: Path) -> None:
        """Test handling of quotes in agent.yaml."""
        agent_yaml = tmp_path / "agent.yaml"
        agent_yaml.write_text("version: '0.1.0'", encoding="utf-8")

        version_manager.update_files(tmp_path, "v0.2.0")

        assert "version: '0.2.0'" in agent_yaml.read_text()

    def test_update_agent_yaml_no_quotes(self, version_manager: VersionManager, tmp_path: Path) -> None:
        """Test handling of no quotes in agent.yaml."""
        agent_yaml = tmp_path / "agent.yaml"
        agent_yaml.write_text("version: 0.1.0", encoding="utf-8")

        version_manager.update_files(tmp_path, "v0.2.0")

        # It should preserve structure roughly, but our regex replacement adds back whatever quotes were captured.
        # If group 2 and 4 were empty, it replaces with just the version.
        assert "version: 0.2.0" in agent_yaml.read_text()

    def test_update_agent_yaml_append(self, version_manager: VersionManager, tmp_path: Path) -> None:
        """Test appending version to agent.yaml if key missing."""
        agent_yaml = tmp_path / "agent.yaml"
        agent_yaml.write_text("name: test\n", encoding="utf-8")

        version_manager.update_files(tmp_path, "v0.2.0")

        content = agent_yaml.read_text()
        assert 'version: "0.2.0"' in content
        assert "name: test" in content

    def test_update_changelog_append_end(self, version_manager: VersionManager, tmp_path: Path) -> None:
        """Test appending to changelog if no headers found."""
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text("# Title\nSome text.", encoding="utf-8")

        version_manager.update_files(tmp_path, "v0.2.0")

        content = changelog.read_text()
        assert "# Title" in content
        assert "## [0.2.0] -" in content

    def test_update_agent_yaml_complex_format(self, version_manager: VersionManager, tmp_path: Path) -> None:
        """Test updating agent.yaml with comments and weird spacing."""
        agent_yaml = tmp_path / "agent.yaml"
        # Spacing, comments, surrounding keys
        content = """
name: "my-agent"
# This is the version
version:    "1.0.0"   # Current version used in prod
description: "Fancy Agent"
"""
        agent_yaml.write_text(content, encoding="utf-8")

        version_manager.update_files(tmp_path, "v1.1.0")

        new_content = agent_yaml.read_text()

        # Verify version updated
        assert 'version:    "1.1.0"' in new_content
        # Verify comment preserved (it's outside the match group 4 if spacing is there)
        assert "# Current version used in prod" in new_content
        # Verify other keys preserved
        assert 'name: "my-agent"' in new_content

    def test_update_changelog_weird_structure(self, version_manager: VersionManager, tmp_path: Path) -> None:
        """Test updating changelog with weird structure."""
        changelog = tmp_path / "CHANGELOG.md"
        # Case where "## [" exists but not at start of line or something weird?
        # Or standard but messy.
        content = """# Changelog
This is a changelog.

## [1.0.0] - 2023-01-01
- First release

Random text
"""
        changelog.write_text(content, encoding="utf-8")

        version_manager.update_files(tmp_path, "v1.1.0")

        new_content = changelog.read_text()
        # Should insert before ## [1.0.0]
        assert "## [1.1.0] -" in new_content
        assert new_content.find("## [1.1.0]") < new_content.find("## [1.0.0]")

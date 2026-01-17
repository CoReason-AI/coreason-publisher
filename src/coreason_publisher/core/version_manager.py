# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_publisher

import re
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

from coreason_publisher.core.git_provider import GitProvider
from coreason_publisher.utils.logger import logger


class BumpType(str, Enum):
    PATCH = "patch"
    MINOR = "minor"
    MAJOR = "major"


class VersionManager:
    """
    Manages semantic versioning logic and file updates.
    """

    def __init__(self, git_provider: GitProvider) -> None:
        self.git_provider = git_provider

    def get_current_version(self, workspace_path: Path) -> Optional[str]:
        """
        Determines the current version from Git tags and agent.yaml.
        Prioritizes Git tags as the source of truth for the last released version.

        Args:
            workspace_path: The root of the repository.

        Returns:
            The version string (e.g., "v1.1.0"), or None if no version exists.
        """
        tag_version = self.git_provider.get_last_tag()

        # Check agent.yaml for consistency, but don't crash if missing (it might be a fresh repo)
        yaml_version = self._read_agent_yaml_version(workspace_path)

        if tag_version and yaml_version:
            if tag_version != yaml_version and tag_version != f"v{yaml_version}":
                logger.warning(
                    f"Version mismatch: Git tag is {tag_version}, but agent.yaml says {yaml_version}. "
                    "Using Git tag as the source of truth."
                )

        if tag_version:
            return tag_version

        # If no tags, we might rely on agent.yaml if it exists?
        # Requirement says: "Input: Reads the last tag from Git".
        # But also: "Initial Version: Default to v0.1.0 if no Git tags or agent.yaml version are detected."
        # This implies if agent.yaml exists, we might respect it?
        # However, for a *release* manager, the previous state is usually defined by the last *release* (tag).
        # If agent.yaml has 0.1.0 but no tag, it means 0.1.0 is the *current* dev version, not the *last released*.
        # So `get_current_version` effectively means "get last released version".

        return None

    def calculate_next_version(self, current_version: Optional[str], bump_type: BumpType) -> str:
        """
        Calculates the next semantic version.

        Args:
            current_version: The current version string (e.g., "v1.1.0").
            bump_type: The type of increment (Patch, Minor, Major).

        Returns:
            The new version string (e.g., "v1.2.0").
        """
        if not current_version:
            logger.info("No current version found. Defaulting to v0.1.0.")
            return "v0.1.0"

        # Strip 'v' prefix if present
        version_str = current_version.lstrip("v")

        try:
            major, minor, patch = map(int, version_str.split("."))
        except ValueError as e:
            logger.error(f"Invalid version format: {current_version}")
            raise ValueError(f"Invalid version format: {current_version}") from e

        if bump_type == BumpType.MAJOR:
            major += 1
            minor = 0
            patch = 0
        elif bump_type == BumpType.MINOR:
            minor += 1
            patch = 0
        elif bump_type == BumpType.PATCH:
            patch += 1

        new_version = f"v{major}.{minor}.{patch}"
        logger.info(f"Calculated next version: {current_version} -> {new_version} ({bump_type.value})")
        return new_version

    def update_files(self, workspace_path: Path, new_version: str) -> None:
        """
        Updates agent.yaml and CHANGELOG.md with the new version.

        Args:
            workspace_path: The root of the repository.
            new_version: The new version string (e.g., "v1.2.0").
        """
        logger.info(f"Updating version files in {workspace_path} to {new_version}")

        self._update_agent_yaml(workspace_path, new_version)
        self._update_changelog(workspace_path, new_version)

    def _read_agent_yaml_version(self, workspace_path: Path) -> Optional[str]:
        yaml_path = workspace_path / "agent.yaml"
        if not yaml_path.exists():
            return None

        try:
            content = yaml_path.read_text(encoding="utf-8")
            # Simple regex parse to avoid yaml dependency if possible, or use simple string search?
            # Requirement assumes "root-level key version: 'x.y.z'".
            # Let's verify if we can assume standard format.
            # Using regex is safer than string split.
            match = re.search(r"^version:\s*[\"']?([^\"'\s]+)[\"']?", content, re.MULTILINE)
            if match:
                return match.group(1)
        except Exception as e:
            logger.warning(f"Failed to read agent.yaml: {e}")

        return None

    def _update_agent_yaml(self, workspace_path: Path, new_version: str) -> None:
        yaml_path = workspace_path / "agent.yaml"
        version_clean = new_version.lstrip("v")

        if not yaml_path.exists():
            logger.info(f"Creating {yaml_path}")
            yaml_path.write_text(f'version: "{version_clean}"\n', encoding="utf-8")
            return

        content = yaml_path.read_text(encoding="utf-8")

        # Replace version
        # Look for version: ...
        pattern = r"^(version:\s*)([\"']?)([^\"'\s]+)([\"']?)"
        replacement = f"\\g<1>\\g<2>{version_clean}\\g<4>"

        if re.search(pattern, content, re.MULTILINE):
            new_content = re.sub(pattern, replacement, content, count=1, flags=re.MULTILINE)
        else:
            # Append if not found
            new_content = content + f'\nversion: "{version_clean}"\n'

        yaml_path.write_text(new_content, encoding="utf-8")
        logger.info(f"Updated {yaml_path}")

    def _update_changelog(self, workspace_path: Path, new_version: str) -> None:
        changelog_path = workspace_path / "CHANGELOG.md"
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        header = f"## [{new_version.lstrip('v')}] - {date_str}"

        if not changelog_path.exists():
            logger.info(f"Creating {changelog_path}")
            content = "# Changelog\n\nAll notable changes to this project will be documented in this file.\n\n"
            content += f"{header}\n\n- Initial release.\n"
            changelog_path.write_text(content, encoding="utf-8")
            return

        content = changelog_path.read_text(encoding="utf-8")
        lines = content.splitlines()

        # Find where to insert. Usually after the main title.
        # If "## [" exists, insert before the first one.
        # Else append to end or after title.

        insert_idx = -1
        for i, line in enumerate(lines):
            if line.startswith("## ["):
                insert_idx = i
                break

        new_entry = f"{header}\n\n- No changes documented.\n"

        if insert_idx != -1:
            lines.insert(insert_idx, new_entry)
            # Add an extra newline if needed
            if lines[insert_idx + 1].strip() != "":
                lines.insert(insert_idx + 1, "")
        else:
            # Assuming standard Keep a Changelog format where title is at top.
            # If we didn't find any version headers, append after header or at end.
            # Let's try to find the first non-empty line after title?
            # Simply appending if no previous versions might be safest if structure is unknown.
            lines.append("")
            lines.append(new_entry)

        changelog_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        logger.info(f"Updated {changelog_path}")

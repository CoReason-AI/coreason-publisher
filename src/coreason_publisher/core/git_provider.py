# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_publisher

from abc import ABC, abstractmethod
from typing import Optional


class GitProvider(ABC):
    """Abstract base class for Git providers (GitLab, GitHub, etc.)."""

    @abstractmethod
    def create_merge_request(self, source_branch: str, target_branch: str, title: str, description: str) -> int:
        """
        Creates a merge request.

        Returns:
            The ID of the created merge request.
        """
        pass  # pragma: no cover

    @abstractmethod
    def merge_merge_request(self, mr_id: int) -> None:
        """
        Merges the specified merge request.

        Args:
            mr_id: The ID of the merge request to merge.
        """
        pass  # pragma: no cover

    @abstractmethod
    def create_tag(self, tag_name: str, ref: str, message: str) -> None:
        """
        Creates a git tag.

        Args:
            tag_name: The name of the tag (e.g., v1.0.0).
            ref: The commit SHA or branch name to tag.
            message: The tag message.
        """
        pass  # pragma: no cover

    @abstractmethod
    def get_last_tag(self) -> Optional[str]:
        """
        Retrieves the latest tag from the repository.

        Returns:
            The name of the last tag, or None if no tags exist.
        """
        pass  # pragma: no cover

    @abstractmethod
    def post_comment(self, mr_id: int, body: str) -> None:
        """
        Posts a comment to a merge request.

        Args:
            mr_id: The ID of the merge request.
            body: The content of the comment.
        """
        pass  # pragma: no cover

    @abstractmethod
    def get_merge_request_status(self, mr_id: int) -> str:
        """
        Gets the status of a merge request.

        Args:
            mr_id: The ID of the merge request.

        Returns:
            The status string (e.g., 'opened', 'merged', 'closed').
        """
        pass  # pragma: no cover

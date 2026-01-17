# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_publisher

from typing import Optional

import gitlab
from gitlab.v4.objects import Project

from coreason_publisher.config import PublisherConfig
from coreason_publisher.core.git_provider import GitProvider
from coreason_publisher.utils.logger import logger


class GitLabProvider(GitProvider):
    """GitLab implementation of the GitProvider interface."""

    def __init__(self, project_id: str | int, config: Optional[PublisherConfig] = None) -> None:
        """
        Initialize the GitLab provider.

        Args:
            project_id: The ID or path of the GitLab project.
            config: Optional configuration object. If not provided, will instantiate one.
        """
        if config is None:
            # Fallback for existing tests or usages that might not pass config yet,
            # though ideally we should require it.
            # However, since we are refactoring, we can instantiate it here to pick up env vars.
            config = PublisherConfig()

        self.config = config

        if not self.config.gitlab_token:
            logger.error("GITLAB_TOKEN not set in config")
            raise ValueError("GITLAB_TOKEN not set in config")

        self.token = self.config.gitlab_token.get_secret_value()
        self.url = self.config.gitlab_url
        self.gl = gitlab.Gitlab(url=self.url, private_token=self.token)
        self.project_id = project_id
        self._project: Optional[Project] = None

    @property
    def project(self) -> Project:
        """Lazy loads the project object."""
        if self._project is None:
            try:
                self._project = self.gl.projects.get(self.project_id)
            except gitlab.GitlabGetError as e:
                logger.error(f"Failed to get project {self.project_id}: {e}")
                raise RuntimeError(f"Failed to get project {self.project_id}: {e}") from e
        return self._project

    def create_merge_request(self, source_branch: str, target_branch: str, title: str, description: str) -> int:
        """Creates a merge request."""
        logger.info(f"Creating MR: {title} ({source_branch} -> {target_branch})")
        try:
            mr = self.project.mergerequests.create(
                {
                    "source_branch": source_branch,
                    "target_branch": target_branch,
                    "title": title,
                    "description": description,
                }
            )
            logger.info(f"MR created successfully: {mr.web_url}")
            return int(mr.iid)  # Use internal ID (IID) for project-scoped references
        except gitlab.GitlabCreateError as e:
            logger.error(f"Failed to create MR: {e}")
            raise RuntimeError(f"Failed to create MR: {e}") from e

    def merge_merge_request(self, mr_id: int) -> None:
        """Merges the specified merge request."""
        logger.info(f"Merging MR {mr_id}")
        try:
            mr = self.project.mergerequests.get(mr_id)
            mr.merge()
            logger.info(f"MR {mr_id} merged successfully")
        except (gitlab.GitlabGetError, gitlab.GitlabMRClosedError) as e:
            logger.error(f"Failed to merge MR {mr_id}: {e}")
            raise RuntimeError(f"Failed to merge MR {mr_id}: {e}") from e

    def create_tag(self, tag_name: str, ref: str, message: str) -> None:
        """Creates a git tag."""
        logger.info(f"Creating tag {tag_name} at {ref}")
        try:
            self.project.tags.create({"tag_name": tag_name, "ref": ref, "message": message})
            logger.info(f"Tag {tag_name} created successfully")
        except gitlab.GitlabCreateError as e:
            logger.error(f"Failed to create tag {tag_name}: {e}")
            raise RuntimeError(f"Failed to create tag {tag_name}: {e}") from e

    def get_last_tag(self) -> Optional[str]:
        """Retrieves the latest tag from the repository."""
        try:
            tags = self.project.tags.list(order_by="updated", sort="desc", per_page=1)
            if tags:
                return str(tags[0].name)
            return None
        except gitlab.GitlabListError as e:
            logger.error(f"Failed to list tags: {e}")
            raise RuntimeError(f"Failed to list tags: {e}") from e

    def post_comment(self, mr_id: int, body: str) -> None:
        """Posts a comment to a merge request."""
        logger.info(f"Posting comment to MR {mr_id}")
        try:
            mr = self.project.mergerequests.get(mr_id)
            mr.notes.create({"body": body})
            logger.info(f"Comment posted to MR {mr_id}")
        except (gitlab.GitlabGetError, gitlab.GitlabCreateError) as e:
            logger.error(f"Failed to post comment to MR {mr_id}: {e}")
            raise RuntimeError(f"Failed to post comment to MR {mr_id}: {e}") from e

    def get_merge_request_status(self, mr_id: int) -> str:
        """Gets the status of a merge request."""
        try:
            mr = self.project.mergerequests.get(mr_id)
            return str(mr.state)
        except gitlab.GitlabGetError as e:
            logger.error(f"Failed to get MR {mr_id}: {e}")
            raise RuntimeError(f"Failed to get MR {mr_id}: {e}") from e

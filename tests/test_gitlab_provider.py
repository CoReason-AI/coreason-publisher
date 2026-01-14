# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_publisher

import os
from typing import Generator
from unittest.mock import MagicMock, patch

import gitlab
import pytest
from coreason_publisher.core.gitlab_provider import GitLabProvider


@pytest.fixture  # type: ignore[misc]
def mock_gitlab() -> Generator[MagicMock, None, None]:
    with patch("coreason_publisher.core.gitlab_provider.gitlab.Gitlab") as mock:
        yield mock


@pytest.fixture  # type: ignore[misc]
def provider(mock_gitlab: MagicMock) -> GitLabProvider:
    with patch.dict(os.environ, {"GITLAB_TOKEN": "dummy_token"}):
        return GitLabProvider(project_id="test/project")


def test_init_raises_without_token() -> None:
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="GITLAB_TOKEN environment variable not set"):
            GitLabProvider(project_id="test/project")


def test_project_property(provider: GitLabProvider, mock_gitlab: MagicMock) -> None:
    mock_project = MagicMock()
    mock_gitlab.return_value.projects.get.return_value = mock_project

    assert provider.project == mock_project
    mock_gitlab.return_value.projects.get.assert_called_once_with("test/project")

    # Test caching
    assert provider.project == mock_project
    assert mock_gitlab.return_value.projects.get.call_count == 1


def test_project_property_error(provider: GitLabProvider, mock_gitlab: MagicMock) -> None:
    mock_gitlab.return_value.projects.get.side_effect = gitlab.GitlabGetError(response_code=404)
    with pytest.raises(RuntimeError, match="Failed to get project"):
        _ = provider.project


def test_create_merge_request_success(provider: GitLabProvider) -> None:
    mock_project = MagicMock()
    provider._project = mock_project
    mock_mr = MagicMock()
    mock_mr.iid = 123
    mock_mr.web_url = "http://gitlab.com/test/project/merge_requests/123"
    mock_project.mergerequests.create.return_value = mock_mr

    mr_id = provider.create_merge_request("feature", "main", "Title", "Desc")

    assert mr_id == 123
    mock_project.mergerequests.create.assert_called_once_with(
        {
            "source_branch": "feature",
            "target_branch": "main",
            "title": "Title",
            "description": "Desc",
        }
    )


def test_create_merge_request_error(provider: GitLabProvider) -> None:
    mock_project = MagicMock()
    provider._project = mock_project
    mock_project.mergerequests.create.side_effect = gitlab.GitlabCreateError(response_code=400)

    with pytest.raises(RuntimeError, match="Failed to create MR"):
        provider.create_merge_request("feature", "main", "Title", "Desc")


def test_merge_merge_request_success(provider: GitLabProvider) -> None:
    mock_project = MagicMock()
    provider._project = mock_project
    mock_mr = MagicMock()
    mock_project.mergerequests.get.return_value = mock_mr

    provider.merge_merge_request(123)

    mock_project.mergerequests.get.assert_called_once_with(123)
    mock_mr.merge.assert_called_once()


def test_merge_merge_request_error(provider: GitLabProvider) -> None:
    mock_project = MagicMock()
    provider._project = mock_project
    mock_project.mergerequests.get.side_effect = gitlab.GitlabGetError(response_code=404)

    with pytest.raises(RuntimeError, match="Failed to merge MR"):
        provider.merge_merge_request(123)


def test_create_tag_success(provider: GitLabProvider) -> None:
    mock_project = MagicMock()
    provider._project = mock_project

    provider.create_tag("v1.0.0", "sha123", "Release v1.0.0")

    mock_project.tags.create.assert_called_once_with(
        {
            "tag_name": "v1.0.0",
            "ref": "sha123",
            "message": "Release v1.0.0",
        }
    )


def test_create_tag_error(provider: GitLabProvider) -> None:
    mock_project = MagicMock()
    provider._project = mock_project
    mock_project.tags.create.side_effect = gitlab.GitlabCreateError(response_code=400)

    with pytest.raises(RuntimeError, match="Failed to create tag"):
        provider.create_tag("v1.0.0", "sha123", "Release v1.0.0")


def test_get_last_tag_success(provider: GitLabProvider) -> None:
    mock_project = MagicMock()
    provider._project = mock_project
    mock_tag = MagicMock()
    mock_tag.name = "v1.0.0"
    mock_project.tags.list.return_value = [mock_tag]

    last_tag = provider.get_last_tag()

    assert last_tag == "v1.0.0"
    mock_project.tags.list.assert_called_once_with(order_by="updated", sort="desc", per_page=1)


def test_get_last_tag_none(provider: GitLabProvider) -> None:
    mock_project = MagicMock()
    provider._project = mock_project
    mock_project.tags.list.return_value = []

    last_tag = provider.get_last_tag()

    assert last_tag is None


def test_get_last_tag_error(provider: GitLabProvider) -> None:
    mock_project = MagicMock()
    provider._project = mock_project
    mock_project.tags.list.side_effect = gitlab.GitlabListError(response_code=500)

    with pytest.raises(RuntimeError, match="Failed to list tags"):
        provider.get_last_tag()


def test_post_comment_success(provider: GitLabProvider) -> None:
    mock_project = MagicMock()
    provider._project = mock_project
    mock_mr = MagicMock()
    mock_project.mergerequests.get.return_value = mock_mr

    provider.post_comment(123, "Test comment")

    mock_project.mergerequests.get.assert_called_once_with(123)
    mock_mr.notes.create.assert_called_once_with({"body": "Test comment"})


def test_post_comment_error(provider: GitLabProvider) -> None:
    mock_project = MagicMock()
    provider._project = mock_project
    mock_project.mergerequests.get.side_effect = gitlab.GitlabGetError(response_code=404)

    with pytest.raises(RuntimeError, match="Failed to post comment"):
        provider.post_comment(123, "Test comment")


def test_get_merge_request_status_success(provider: GitLabProvider) -> None:
    mock_project = MagicMock()
    provider._project = mock_project
    mock_mr = MagicMock()
    mock_mr.state = "opened"
    mock_project.mergerequests.get.return_value = mock_mr

    status = provider.get_merge_request_status(123)

    assert status == "opened"
    mock_project.mergerequests.get.assert_called_once_with(123)


def test_get_merge_request_status_error(provider: GitLabProvider) -> None:
    mock_project = MagicMock()
    provider._project = mock_project
    mock_project.mergerequests.get.side_effect = gitlab.GitlabGetError(response_code=404)

    with pytest.raises(RuntimeError, match="Failed to get MR"):
        provider.get_merge_request_status(123)


# --- Edge Case & Complex Scenario Tests ---


def test_api_unauthorized(provider: GitLabProvider, mock_gitlab: MagicMock) -> None:
    """Test handling of 401 Unauthorized error."""
    mock_project = MagicMock()
    provider._project = mock_project
    # Simulate 401 on MR creation
    mock_project.mergerequests.create.side_effect = gitlab.GitlabAuthenticationError(
        response_code=401, error_message="Unauthorized"
    )

    # Depending on implementation, this might raise RuntimeError (if wrapped) or the original error
    # Currently, create_merge_request only catches GitlabCreateError.
    # GitlabAuthenticationError usually inherits from GitlabError, not GitlabCreateError.
    # Let's see what happens. If it fails, we fix the code.
    with pytest.raises(gitlab.GitlabAuthenticationError):
        provider.create_merge_request("source", "target", "Title", "Desc")


def test_create_merge_request_conflict(provider: GitLabProvider) -> None:
    """Test handling of 409 Conflict (e.g., MR already exists)."""
    mock_project = MagicMock()
    provider._project = mock_project
    # 409 often raises GitlabCreateError in python-gitlab for creation calls
    mock_project.mergerequests.create.side_effect = gitlab.GitlabCreateError(
        response_code=409, error_message="Conflict"
    )

    with pytest.raises(RuntimeError, match="Failed to create MR"):
        provider.create_merge_request("source", "target", "Title", "Desc")


def test_server_error(provider: GitLabProvider) -> None:
    """Test handling of 500 Server Error."""
    mock_project = MagicMock()
    provider._project = mock_project
    mock_project.mergerequests.create.side_effect = gitlab.GitlabHttpError(
        response_code=500, error_message="Server Error"
    )

    with pytest.raises(gitlab.GitlabHttpError):
        provider.create_merge_request("source", "target", "Title", "Desc")


def test_special_characters(provider: GitLabProvider) -> None:
    """Test that special characters are passed correctly to the API."""
    mock_project = MagicMock()
    provider._project = mock_project
    mock_mr = MagicMock()
    mock_mr.iid = 999
    mock_project.mergerequests.create.return_value = mock_mr

    title = 'Title with "quotes" and emojis 🚀'
    description = "Desc with \n newlines and \t tabs"
    source = "feat/special-chars"
    target = "main"

    provider.create_merge_request(source, target, title, description)

    mock_project.mergerequests.create.assert_called_once_with(
        {
            "source_branch": source,
            "target_branch": target,
            "title": title,
            "description": description,
        }
    )


def test_complex_lifecycle_scenario(provider: GitLabProvider) -> None:
    """
    Simulate a full MR lifecycle:
    1. Create MR
    2. Post Comment
    3. Check Status
    4. Merge
    """
    mock_project = MagicMock()
    provider._project = mock_project

    # Setup MR mock
    mock_mr = MagicMock()
    mock_mr.iid = 101
    mock_mr.state = "opened"

    # 1. Create
    mock_project.mergerequests.create.return_value = mock_mr
    mr_id = provider.create_merge_request("feat/x", "main", "Feat X", "Desc")
    assert mr_id == 101

    # Setup Get MR mock for subsequent calls
    mock_project.mergerequests.get.return_value = mock_mr

    # 2. Post Comment
    provider.post_comment(mr_id, "LGTM")
    mock_mr.notes.create.assert_called_once_with({"body": "LGTM"})

    # 3. Check Status
    status = provider.get_merge_request_status(mr_id)
    assert status == "opened"

    # 4. Merge
    provider.merge_merge_request(mr_id)
    mock_mr.merge.assert_called_once()

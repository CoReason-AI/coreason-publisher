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

from coreason_identity.models import UserContext


class FoundryClient(ABC):
    """Abstract base class for interacting with the CoReason Foundry service."""

    @abstractmethod
    def submit_for_review(self, draft_id: str, type: str, user_context: UserContext) -> None:
        """
        Submits a draft for review.

        Args:
            draft_id: The ID of the draft to submit.
            type: The type of release (e.g., 'minor', 'patch').
            user_context: The user context of the submitter.

        Raises:
            RuntimeError: If the submission fails.
        """
        pass  # pragma: no cover

    @abstractmethod
    def approve_release(self, mr_id: int, signature: str, user_context: UserContext) -> None:
        """
        Approves a release.

        Args:
            mr_id: The ID of the merge request associated with the release.
            signature: The cryptographic signature approving the release.
            user_context: The user context of the approver.

        Raises:
            RuntimeError: If the approval fails.
        """
        pass  # pragma: no cover

    @abstractmethod
    def reject_release(self, draft_id: str, reason: str) -> None:
        """
        Rejects a release draft.

        Args:
            draft_id: The ID of the Foundry draft.
            reason: The reason for rejection.
        """
        pass  # pragma: no cover

    @abstractmethod
    def get_draft_status(self, draft_id: str) -> str:
        """
        Retrieves the status of a draft.

        Args:
            draft_id: The ID of the draft.

        Returns:
            The status of the draft (e.g., 'PENDING_SRB', 'RELEASED').

        Raises:
            RuntimeError: If the status cannot be retrieved.
        """
        pass  # pragma: no cover

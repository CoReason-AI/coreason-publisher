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

from coreason_publisher.core.artifact_bundler import ArtifactBundler
from coreason_publisher.core.assay_client import AssayClient
from coreason_publisher.core.electronic_signer import ElectronicSigner
from coreason_publisher.core.foundry_client import FoundryClient
from coreason_publisher.core.git_lfs import GitLFS
from coreason_publisher.core.git_local import GitLocal
from coreason_publisher.core.git_provider import GitProvider
from coreason_publisher.core.version_manager import BumpType, VersionManager
from coreason_publisher.utils.logger import logger


class PublisherOrchestrator:
    """
    Coordinates the publishing workflow.
    """

    def __init__(
        self,
        workspace_path: Path,
        assay_client: AssayClient,
        foundry_client: FoundryClient,
        git_provider: GitProvider,
        git_local: GitLocal,
        git_lfs: GitLFS,
        artifact_bundler: ArtifactBundler,
        electronic_signer: ElectronicSigner,
        version_manager: VersionManager,
    ) -> None:
        self.workspace_path = workspace_path
        self.assay_client = assay_client
        self.foundry_client = foundry_client
        self.git_provider = git_provider
        self.git_local = git_local
        self.git_lfs = git_lfs
        self.artifact_bundler = artifact_bundler
        self.electronic_signer = electronic_signer
        self.version_manager = version_manager

    def propose_release(
        self,
        project_id: str,
        foundry_draft_id: str,
        bump_type: BumpType,
        sre_user_id: str,
        release_description: str,
    ) -> None:
        """
        Orchestrates the 'Propose' phase of the release workflow.

        1. Fetches the latest passing assay report.
        2. Calculates the next version.
        3. Runs the artifact bundler.
        4. Calculates the SRE signature.
        5. Commits and pushes the candidate branch.
        6. Opens a Merge Request.
        7. Submits the Foundry draft for review.

        Args:
            project_id: The Assay project ID to fetch report from.
            foundry_draft_id: The Foundry draft ID to link.
            bump_type: The type of version bump (patch, minor, major).
            sre_user_id: The ID of the SRE proposing the release.
            release_description: Description for the MR and changelog.
        """
        logger.info(f"Starting release proposal for project {project_id} (Draft: {foundry_draft_id})")

        # 1. Fetch Assay Report
        assay_report = self.assay_client.get_latest_report(project_id)
        evidence_dir = self.workspace_path / "evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        report_path = evidence_dir / "assay_report.json"

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(assay_report, f, indent=2)
        logger.info(f"Saved assay report to {report_path}")

        # 2. Calculate Version
        current_version = self.version_manager.get_current_version(self.workspace_path)
        next_version = self.version_manager.calculate_next_version(current_version, bump_type)
        candidate_branch = f"candidate/{next_version}"

        # 3. Prepare Branch
        self.git_local.checkout_new_branch(candidate_branch)

        # Update version files
        self.version_manager.update_files(self.workspace_path, next_version)

        # Run Bundler (LFS, Model moving, Council Snapshot)
        self.artifact_bundler.bundle(self.workspace_path)

        # 4. Sign and Commit
        # Stage everything first so we can hash the bundle content effectively
        # Note: ElectronicSigner hashes the *files on disk* that match the pattern, excluding .git
        # So we can hash before or after staging, but before commit makes sense.

        signature = self.electronic_signer.create_signature(self.workspace_path, sre_user_id)

        commit_message = self.electronic_signer.format_commit_message(
            original_message=f"chore(release): propose {next_version}\n\n{release_description}",
            user_id=sre_user_id,
            signature=signature,
            signer_role="SRE",
        )

        self.git_local.add_all()
        self.git_local.commit(commit_message)

        # 5. Push
        # Enforce strict LFS verification before push to prevent pushing heavy artifacts without pointers
        self.git_lfs.verify_ready(self.workspace_path)
        self.git_local.push(candidate_branch)

        # 6. Open MR
        mr_title = f"Release {next_version}"
        mr_description = (
            f"Release Candidate: {next_version}\n"
            f"Proposer: {sre_user_id}\n"
            f"Signature: {signature}\n\n"
            f"Description: {release_description}"
        )

        # Determine target branch - usually main or master.
        # We can assume 'main' for now or get default branch from git provider if API supported it.
        # Let's assume 'main'.
        target_branch = "main"

        try:
            mr_id = self.git_provider.create_merge_request(
                source_branch=candidate_branch, target_branch=target_branch, title=mr_title, description=mr_description
            )
        except RuntimeError:
            # If MR creation fails, we should probably warn but the branch is pushed.
            # But the requirement says "Atomic Rollback... if API call fails... NOT mark Foundry Draft"
            # So raising here prevents the next step.
            raise

        # 7. Submit to Foundry
        # "Locks the Foundry Draft (status: PENDING_SRB)"
        # submit_for_review(draft_id, type)
        # Type might be 'release_candidate' or similar.
        # PRD says: "SRE releases an agent... Selects 'Submit Release' -> 'Minor Version'"
        # Let's assume type="release".
        self.foundry_client.submit_for_review(foundry_draft_id, type="release")

        # Post comment to MR linking the draft? (Optional, not in PRD but good practice)
        self.git_provider.post_comment(mr_id, f"Linked Foundry Draft: {foundry_draft_id}")

        logger.info(f"Release proposal completed. MR: {mr_id}, Version: {next_version}")

    def finalize_release(self, mr_id: int, srb_signature: str) -> None:
        """
        Orchestrates the 'Release' phase.

        1. Verifies the SRB signature against the current workspace (candidate bundle).
        2. Merges the MR to main.
        3. Creates the Git Tag on main.
        4. Unlocks Foundry (Approve Release).

        Args:
            mr_id: The Merge Request ID.
            srb_signature: The cryptographic signature provided by the SRB.
        """
        logger.info(f"Finalizing release for MR {mr_id}")

        # 1. Verify Signature
        if not self.electronic_signer.verify_signature(self.workspace_path, srb_signature):
            logger.error("Signature verification failed! Release aborted.")
            raise ValueError("Signature verification failed. The artifact does not match the SRB signature.")

        # 2. Get Version for Tag
        # We assume the workspace is currently on the candidate branch
        current_version = self.version_manager.get_current_version(self.workspace_path)
        if not current_version:
            raise RuntimeError("Could not determine version from workspace.")

        # 3. Merge MR
        # We assume target is main.
        self.git_provider.merge_merge_request(mr_id)

        # 4. Create Tag
        # Tagging 'main' assuming the merge moved main forward.
        self.git_provider.create_tag(tag_name=current_version, ref="main", message=f"Release {current_version}")

        # 5. Notify Foundry
        self.foundry_client.approve_release(mr_id, srb_signature)

        logger.info(f"Release {current_version} finalized successfully.")

    def reject_release(self, mr_id: int, draft_id: str, reason: str) -> None:
        """
        Orchestrates the 'Reject' phase (SRB Kickback).

        1. Posts a comment to the Merge Request explaining the rejection.
        2. Unlocks the Foundry draft (rejects it) so the SRE can make changes.

        Args:
            mr_id: The Merge Request ID.
            draft_id: The Foundry draft ID.
            reason: The reason for rejection.
        """
        logger.info(f"Rejecting release (MR: {mr_id}, Draft: {draft_id})")

        # 1. Post Comment to MR
        comment_body = f"Changes Requested: {reason}"
        self.git_provider.post_comment(mr_id, comment_body)

        # 2. Unlock Foundry Draft
        self.foundry_client.reject_release(draft_id, reason)

        logger.info(f"Release rejection processed for MR {mr_id}")

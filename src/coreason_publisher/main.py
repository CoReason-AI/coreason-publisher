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
from typing import Annotated, Optional

import typer

from coreason_publisher.config import PublisherConfig
from coreason_publisher.core.artifact_bundler import ArtifactBundler
from coreason_publisher.core.certificate_generator import CertificateGenerator
from coreason_publisher.core.council_snapshot import CouncilSnapshot
from coreason_publisher.core.electronic_signer import ElectronicSigner
from coreason_publisher.core.git_lfs import GitLFS
from coreason_publisher.core.git_local import GitLocal
from coreason_publisher.core.gitlab_provider import GitLabProvider
from coreason_publisher.core.http_assay_client import HttpAssayClient
from coreason_publisher.core.http_foundry_client import HttpFoundryClient
from coreason_publisher.core.orchestrator import PublisherOrchestrator
from coreason_publisher.core.remote_storage import MockStorageProvider
from coreason_publisher.core.version_manager import BumpType, VersionManager
from coreason_publisher.utils.logger import logger

app = typer.Typer(
    help="Coreason Publisher: The Regulatory Gatekeeper & Artifact Packager",
    no_args_is_help=True,
)


def get_orchestrator(
    workspace_path: Optional[Path] = None, config: Optional[PublisherConfig] = None
) -> PublisherOrchestrator:
    """Dependency Injection for the Orchestrator."""
    try:
        if workspace_path is None:
            workspace_path = Path.cwd()

        # PublisherConfig now reads from environment variables
        if config is None:
            config = PublisherConfig()

        # Infrastructure
        git_local = GitLocal(workspace_path)

        # Use gitlab_project_id from config or fallback/error
        gitlab_project_id = config.gitlab_project_id
        if not gitlab_project_id:
            logger.warning("GITLAB_PROJECT_ID not set. GitLab integration may fail.")
            gitlab_project_id = "0"  # Dummy if not set, will fail later if used

        # We need to update GitLabProvider to potentially take token from config?
        # The GitLabProvider currently uses os.getenv("GITLAB_TOKEN") in its __init__ (based on memory/assumption)
        # We should check if we should refactor GitLabProvider as well.
        # But for now, let's stick to what we have or pass token if the provider accepts it.
        # Assuming GitLabProvider accepts project_id.
        git_provider = GitLabProvider(project_id=gitlab_project_id, config=config)

        assay_client = HttpAssayClient(config=config)
        foundry_client = HttpFoundryClient(config=config)

        # Components
        git_lfs = GitLFS()
        council_snapshot = CouncilSnapshot()
        # Storage provider configuration could be enhanced
        storage_provider = MockStorageProvider()
        certificate_generator = CertificateGenerator()

        artifact_bundler = ArtifactBundler(
            config=config,
            git_lfs=git_lfs,
            council_snapshot=council_snapshot,
            storage_provider=storage_provider,
            certificate_generator=certificate_generator,
        )

        electronic_signer = ElectronicSigner()
        version_manager = VersionManager(git_provider=git_provider)

        return PublisherOrchestrator(
            workspace_path=workspace_path,
            assay_client=assay_client,
            foundry_client=foundry_client,
            git_provider=git_provider,
            git_local=git_local,
            git_lfs=git_lfs,
            artifact_bundler=artifact_bundler,
            electronic_signer=electronic_signer,
            version_manager=version_manager,
        )
    except Exception as e:
        logger.error(f"Failed to initialize orchestrator: {e}")
        # In a real CLI we might want to exit nicely
        raise typer.Exit(code=1) from e


@app.command()
def propose(
    project_id: Annotated[str, typer.Option("--project-id", "-p", help="Assay Project ID")],
    draft_id: Annotated[str, typer.Option("--draft-id", "-d", help="Foundry Draft ID")],
    bump: Annotated[BumpType, typer.Option("--bump", "-b", help="Version bump type")],
    user_id: Annotated[str, typer.Option("--user-id", "-u", help="SRE User ID")],
    description: Annotated[
        str, typer.Option("--description", "-m", help="Release description")
    ] = "No description provided",
) -> None:
    """
    Propose a new release (SRE).
    Bundles artifacts, calculates version, signs candidate, and opens MR.
    """
    logger.info(f"Command: propose release for project {project_id}")
    orchestrator = get_orchestrator()
    try:
        orchestrator.propose_release(
            project_id=project_id,
            foundry_draft_id=draft_id,
            bump_type=bump,
            sre_user_id=user_id,
            release_description=description,
        )
        typer.secho("Release proposal submitted successfully!", fg=typer.colors.GREEN)
    except Exception as e:
        logger.exception("Propose failed")
        typer.secho(f"Error: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from e


@app.command()
def release(
    mr_id: Annotated[int, typer.Option("--mr-id", help="Merge Request ID")],
    signature: Annotated[str, typer.Option("--signature", help="SRB Signature")],
    srb_user_id: Annotated[str, typer.Option("--srb-user-id", "-u", help="SRB User ID")],
) -> None:
    """
    Finalize a release (System/SRB).
    Verifies signature, merges MR, tags release, and approves in Foundry.
    """
    logger.info(f"Command: finalize release for MR {mr_id}")
    orchestrator = get_orchestrator()
    try:
        orchestrator.finalize_release(mr_id=mr_id, srb_signature=signature, srb_user_id=srb_user_id)
        typer.secho("Release finalized successfully!", fg=typer.colors.GREEN)
    except Exception as e:
        logger.exception("Release failed")
        typer.secho(f"Error: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from e


@app.command()
def reject(
    mr_id: Annotated[int, typer.Option("--mr-id", help="Merge Request ID")],
    draft_id: Annotated[str, typer.Option("--draft-id", "-d", help="Foundry Draft ID")],
    reason: Annotated[str, typer.Option("--reason", "-r", help="Reason for rejection")],
) -> None:
    """
    Reject a release (SRB Kickback).
    Posts a comment to the MR and unlocks the Foundry draft.
    """
    logger.info(f"Command: reject release for MR {mr_id}")
    orchestrator = get_orchestrator()
    try:
        orchestrator.reject_release(mr_id=mr_id, draft_id=draft_id, reason=reason)
        typer.secho("Release rejected successfully!", fg=typer.colors.GREEN)
    except Exception as e:
        logger.exception("Reject failed")
        typer.secho(f"Error: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from e


def main() -> None:
    """Entry point for the application script."""
    app()


if __name__ == "__main__":  # pragma: no cover
    main()

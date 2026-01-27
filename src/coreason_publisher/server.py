# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_publisher

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel, Field

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


class ProposeRequest(BaseModel):
    """Request model for proposing a release."""
    project_id: str = Field(..., description="Assay Project ID")
    draft_id: str = Field(..., description="Foundry Draft ID")
    bump_type: BumpType = Field(..., description="Version bump type")
    user_id: str = Field(..., description="SRE User ID")
    description: str = Field(default="No description provided", description="Release description")


class ReleaseRequest(BaseModel):
    """Request model for finalizing a release."""
    mr_id: int = Field(..., description="Merge Request ID")
    srb_signature: str = Field(..., description="SRB Signature")
    srb_user_id: str = Field(..., description="SRB User ID")


class RejectRequest(BaseModel):
    """Request model for rejecting a release."""
    mr_id: int = Field(..., description="Merge Request ID")
    draft_id: str = Field(..., description="Foundry Draft ID")
    reason: str = Field(..., description="Reason for rejection")


def get_server_orchestrator() -> PublisherOrchestrator:
    """
    Dependency Injection for the Orchestrator (Server variant).
    Based on main.py::get_orchestrator but adapted for server context.
    """
    try:
        workspace_path = Path.cwd()
        config = PublisherConfig()

        # Infrastructure
        git_local = GitLocal(workspace_path)

        # Use gitlab_project_id from config
        gitlab_project_id = config.gitlab_project_id
        if not gitlab_project_id:
            logger.warning("GITLAB_PROJECT_ID not set. GitLab integration may fail.")
            gitlab_project_id = "0"

        git_provider = GitLabProvider(project_id=gitlab_project_id, config=config)
        assay_client = HttpAssayClient(config=config)
        foundry_client = HttpFoundryClient(config=config)

        # Components
        git_lfs = GitLFS()
        council_snapshot = CouncilSnapshot()
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
        logger.exception(f"Failed to initialize orchestrator: {e}")
        raise RuntimeError(f"Failed to initialize orchestrator: {e}") from e


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager to initialize the orchestrator."""
    logger.info("Starting Coreason Publisher Server...")
    try:
        app.state.orchestrator = get_server_orchestrator()
        logger.info("Orchestrator initialized successfully.")
    except Exception as e:
        logger.critical(f"Server startup failed: {e}")
        # In a real server, raising here prevents startup.
        raise
    yield
    logger.info("Shutting down Coreason Publisher Server...")


app = FastAPI(
    title="Coreason Publisher Service",
    description="Governance Workflow Service for Release Management",
    version="0.1.0",
    lifespan=lifespan,
)


@app.post("/propose", status_code=status.HTTP_200_OK)
def propose_release(request_body: ProposeRequest, request: Request):
    """
    Triggers orchestrator.propose_release.
    """
    orchestrator: PublisherOrchestrator = request.app.state.orchestrator
    try:
        orchestrator.propose_release(
            project_id=request_body.project_id,
            foundry_draft_id=request_body.draft_id,
            bump_type=request_body.bump_type,
            sre_user_id=request_body.user_id,
            release_description=request_body.description,
        )
        return {"status": "success", "message": "Release proposal submitted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error in propose_release: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal Server Error")


@app.post("/release", status_code=status.HTTP_200_OK)
def release_release(request_body: ReleaseRequest, request: Request):
    """
    Triggers orchestrator.finalize_release.
    """
    orchestrator: PublisherOrchestrator = request.app.state.orchestrator
    try:
        orchestrator.finalize_release(
            mr_id=request_body.mr_id,
            srb_signature=request_body.srb_signature,
            srb_user_id=request_body.srb_user_id,
        )
        return {"status": "success", "message": "Release finalized successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error in release_release: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal Server Error")


@app.post("/reject", status_code=status.HTTP_200_OK)
def reject_release(request_body: RejectRequest, request: Request):
    """
    Triggers orchestrator.reject_release.
    """
    orchestrator: PublisherOrchestrator = request.app.state.orchestrator
    try:
        orchestrator.reject_release(
            mr_id=request_body.mr_id,
            draft_id=request_body.draft_id,
            reason=request_body.reason,
        )
        return {"status": "success", "message": "Release rejected successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error in reject_release: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal Server Error")


@app.get("/health", status_code=status.HTTP_200_OK)
def health_check(request: Request):
    """
    Verify that Git LFS is installed/ready and the Git provider connection is authenticated.
    """
    orchestrator: PublisherOrchestrator = request.app.state.orchestrator

    # Check Git LFS
    if not orchestrator.git_lfs.is_installed():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Git LFS not installed")

    # Check if LFS is initialized in the workspace
    if not orchestrator.git_lfs.is_initialized(orchestrator.workspace_path):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Git LFS not initialized in workspace")

    # Check Git Provider
    try:
        orchestrator.git_provider.gl.auth()
    except Exception as e:
        logger.error(f"Health check failed for Git Provider: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Git Provider connection failed")

    return {"status": "healthy", "lfs": "ok", "git_provider": "ok"}

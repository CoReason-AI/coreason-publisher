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
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel

from coreason_publisher.core.version_manager import BumpType
from coreason_publisher.core.gitlab_provider import GitLabProvider
from coreason_publisher.main import get_orchestrator
from coreason_publisher.utils.logger import logger


class ProposeRequest(BaseModel):
    project_id: str
    draft_id: str
    bump_type: BumpType
    user_id: str
    description: str


class ReleaseRequest(BaseModel):
    mr_id: int
    srb_signature: str
    srb_user_id: str


class RejectRequest(BaseModel):
    mr_id: int
    draft_id: str
    reason: str


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize the orchestrator on startup."""
    try:
        logger.info("Initializing Publisher Orchestrator...")
        # Dependency Injection via existing factory
        app.state.orchestrator = get_orchestrator()
        logger.info("Publisher Orchestrator initialized successfully.")
    except Exception as e:
        logger.exception("Failed to initialize orchestrator during startup")
        raise RuntimeError("Failed to initialize orchestrator") from e
    yield
    logger.info("Shutting down Publisher Service")


app = FastAPI(
    title="Coreason Governance Service",
    description="The Regulatory Gatekeeper & Artifact Packager",
    version="0.1.0",
    lifespan=lifespan,
)


@app.post("/propose", status_code=status.HTTP_202_ACCEPTED)
def propose_release(request: ProposeRequest, req: Request) -> dict[str, str]:
    """
    Triggers the proposal workflow.
    Executes synchronously in a threadpool to avoid blocking the event loop.
    """
    orchestrator = req.app.state.orchestrator
    try:
        orchestrator.propose_release(
            project_id=request.project_id,
            foundry_draft_id=request.draft_id,
            bump_type=request.bump_type,
            sre_user_id=request.user_id,
            release_description=request.description,
        )
        return {"status": "success", "message": "Release proposal submitted successfully"}
    except ValueError as e:
        logger.warning(f"Bad Request in propose: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        logger.error(f"Runtime Error in propose: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error in propose")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.post("/release", status_code=status.HTTP_200_OK)
def finalize_release(request: ReleaseRequest, req: Request) -> dict[str, str]:
    """
    Triggers the release finalization workflow.
    Executes synchronously in a threadpool.
    """
    orchestrator = req.app.state.orchestrator
    try:
        orchestrator.finalize_release(
            mr_id=request.mr_id,
            srb_signature=request.srb_signature,
            srb_user_id=request.srb_user_id,
        )
        return {"status": "success", "message": "Release finalized successfully"}
    except ValueError as e:
        # Signature mismatch or similar verification failure
        logger.warning(f"Verification failed in release: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        logger.error(f"Runtime Error in release: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error in release")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.post("/reject", status_code=status.HTTP_200_OK)
def reject_release(request: RejectRequest, req: Request) -> dict[str, str]:
    """
    Triggers the release rejection workflow.
    Executes synchronously in a threadpool.
    """
    orchestrator = req.app.state.orchestrator
    try:
        orchestrator.reject_release(
            mr_id=request.mr_id,
            draft_id=request.draft_id,
            reason=request.reason,
        )
        return {"status": "success", "message": "Release rejected successfully"}
    except ValueError as e:
        logger.warning(f"Bad Request in reject: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        logger.error(f"Runtime Error in reject: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error in reject")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/health", status_code=status.HTTP_200_OK)
def health_check(req: Request) -> dict[str, str]:
    """
    Verifies that Git LFS is installed/ready and the Git provider connection is authenticated.
    """
    orchestrator = req.app.state.orchestrator
    try:
        # Check Git LFS
        if not orchestrator.git_lfs.is_initialized(orchestrator.workspace_path):
             raise RuntimeError("Git LFS is not initialized")

        # Check GitLab Provider
        if isinstance(orchestrator.git_provider, GitLabProvider):
             # Authenticate check
             orchestrator.git_provider.gl.auth()

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Service Unhealthy: {e}")

    return {"status": "healthy", "lfs": "ok", "gitlab": "connected"}

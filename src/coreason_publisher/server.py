# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_publisher

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated, cast

from fastapi import Depends, FastAPI, HTTPException, Request, status
from pydantic import BaseModel

from coreason_publisher.config import PublisherConfig
from coreason_publisher.core.orchestrator import PublisherOrchestrator
from coreason_publisher.core.version_manager import BumpType
from coreason_publisher.main import get_orchestrator
from coreason_publisher.utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Initialize the PublisherOrchestrator on startup.
    """
    logger.info("Initializing PublisherOrchestrator...")
    # Initialize with default config (from env) and cwd as workspace
    try:
        config = PublisherConfig()
        orchestrator = get_orchestrator(config=config)
        app.state.orchestrator = orchestrator
        logger.info("PublisherOrchestrator initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize orchestrator: {e}")
        # We might want to let it fail, but usually lifespan exceptions crash the startup, which is good.
        raise
    yield
    logger.info("Shutting down PublisherOrchestrator...")


app = FastAPI(
    title="Coreason Publisher API",
    description="Governance & Release Service",
    version="0.2.0",
    lifespan=lifespan,
)


def get_orch(request: Request) -> PublisherOrchestrator:
    """Dependency to get the orchestrator from app state."""
    return cast(PublisherOrchestrator, request.app.state.orchestrator)


# --- Models ---


class ProposeRequest(BaseModel):
    project_id: str
    draft_id: str
    bump_type: BumpType
    user_id: str
    description: str = "No description provided"


class ReleaseRequest(BaseModel):
    mr_id: int
    srb_signature: str
    srb_user_id: str


class RejectRequest(BaseModel):
    mr_id: int
    draft_id: str
    reason: str


# --- Endpoints ---


@app.post("/propose", status_code=status.HTTP_202_ACCEPTED)
def propose_release(
    req: ProposeRequest, orchestrator: Annotated[PublisherOrchestrator, Depends(get_orch)]
) -> dict[str, str]:
    """
    Triggers orchestrator.propose_release.
    Runs synchronously in a thread pool.
    """
    try:
        orchestrator.propose_release(
            project_id=req.project_id,
            foundry_draft_id=req.draft_id,
            bump_type=req.bump_type,
            sre_user_id=req.user_id,
            release_description=req.description,
        )
        return {"status": "Proposal submitted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e
    except Exception as e:
        logger.exception("Unexpected error in propose_release")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@app.post("/release", status_code=status.HTTP_200_OK)
def finalize_release(
    req: ReleaseRequest, orchestrator: Annotated[PublisherOrchestrator, Depends(get_orch)]
) -> dict[str, str]:
    """
    Triggers orchestrator.finalize_release.
    Runs synchronously in a thread pool.
    """
    try:
        orchestrator.finalize_release(
            mr_id=req.mr_id,
            srb_signature=req.srb_signature,
            srb_user_id=req.srb_user_id,
        )
        return {"status": "Release finalized successfully"}
    except ValueError as e:
        # e.g. Signature verification failed
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e
    except Exception as e:
        logger.exception("Unexpected error in finalize_release")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@app.post("/reject", status_code=status.HTTP_200_OK)
def reject_release(
    req: RejectRequest, orchestrator: Annotated[PublisherOrchestrator, Depends(get_orch)]
) -> dict[str, str]:
    """
    Triggers orchestrator.reject_release.
    Runs synchronously in a thread pool.
    """
    try:
        orchestrator.reject_release(mr_id=req.mr_id, draft_id=req.draft_id, reason=req.reason)
        return {"status": "Release rejected successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e
    except Exception as e:
        logger.exception("Unexpected error in reject_release")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@app.get("/health", status_code=status.HTTP_200_OK)
def health(orchestrator: Annotated[PublisherOrchestrator, Depends(get_orch)]) -> dict[str, str]:
    """
    Verify that Git LFS is installed/ready and the Git provider (GitLab) connection is authenticated.
    """
    # Check LFS
    if not orchestrator.git_lfs.is_initialized(orchestrator.workspace_path):
        # is_initialized checks `git lfs env`
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Git LFS is not initialized or ready."
        )

    # Check Git Provider Authentication
    try:
        # Use get_last_tag as a proxy for connection/auth check
        orchestrator.git_provider.get_last_tag()
    except Exception as e:
        logger.error(f"Health check failed (Git Provider): {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Git Provider check failed: {e}"
        ) from e

    return {"status": "healthy"}

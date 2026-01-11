# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_publisher

import shutil
from pathlib import Path
from typing import List

from coreason_publisher.core.council_snapshot import CouncilSnapshot
from coreason_publisher.core.git_lfs import GitLFS
from coreason_publisher.core.remote_storage import RemoteStorageProvider
from coreason_publisher.utils.logger import logger


class ArtifactBundler:
    """
    Aggregates scattered assets into a standardized deployment folder.
    Handles Model Co-Location, LFS configuration, and Council Snapshots.
    """

    # 100MB
    LFS_THRESHOLD = 100 * 1024 * 1024
    # 70GB
    REMOTE_STORAGE_THRESHOLD = 70 * 1024 * 1024 * 1024

    MODEL_EXTENSIONS = {".safetensors", ".bin", ".pt"}
    MODEL_FILENAMES = {"adapter_config.json"}

    def __init__(
        self,
        git_lfs: GitLFS,
        council_snapshot: CouncilSnapshot,
        storage_provider: RemoteStorageProvider,
    ) -> None:
        self.git_lfs = git_lfs
        self.council_snapshot = council_snapshot
        self.storage_provider = storage_provider

    def bundle(self, workspace_path: Path) -> None:
        """
        Orchestrates the bundling process.

        Args:
            workspace_path: The root of the repository.
        """
        logger.info(f"Starting bundling process in {workspace_path}")

        if not workspace_path.exists():
            raise FileNotFoundError(f"Workspace path {workspace_path} does not exist")

        # 1. Handle Remote Storage (Files > 70GB)
        self._handle_remote_storage(workspace_path)

        # 2. Move Model Artifacts to models/distilled/
        self._move_model_artifacts(workspace_path)

        # 3. Configure LFS (Files > 100MB)
        self._configure_lfs(workspace_path)

        # 4. Generate Council Snapshot
        assay_report = workspace_path / "evidence" / "assay_report.json"
        council_manifest = workspace_path / "council_manifest.lock"
        self.council_snapshot.create_snapshot(assay_report, council_manifest)

        logger.info("Bundling process completed successfully")

    def _handle_remote_storage(self, workspace_path: Path) -> None:
        """
        Scans for files larger than REMOTE_STORAGE_THRESHOLD.
        Uploads them via the storage provider and replaces them with a pointer.
        """
        logger.info("Scanning for ultra-large files (>70GB)...")
        # Recursively find files
        for file_path in workspace_path.rglob("*"):
            try:
                if not file_path.is_file() or file_path.is_symlink():
                    continue

                # Skip .git directory
                if ".git" in file_path.parts:
                    continue

                if file_path.stat().st_size > self.REMOTE_STORAGE_THRESHOLD:
                    logger.info(f"Found ultra-large file: {file_path}")
                    remote_hash = self.storage_provider.upload(file_path)

                    # Create pointer content
                    pointer_content = f"pointer:{remote_hash}\n"

                    # Overwrite file with pointer
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(pointer_content)

                    logger.info(f"Replaced {file_path} with pointer: {remote_hash}")
            except OSError as e:
                logger.warning(f"Could not check file size for {file_path}: {e}")

    def _move_model_artifacts(self, workspace_path: Path) -> None:
        """
        Scans for model artifacts and moves them to models/distilled/.
        """
        distilled_dir = workspace_path / "models" / "distilled"
        distilled_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Scanning for model artifacts to consolidate...")

        # We need to list all files first to avoid infinite loops if we modify directory while iterating?
        # rglob is a generator. Moving files into a subdir of workspace_path might be tricky if we recurse into it.
        # So we should explicitly exclude 'models' dir from source scan.

        files_to_move: List[Path] = []

        for file_path in workspace_path.rglob("*"):
            if not file_path.is_file() or file_path.is_symlink():
                continue

            # Exclude .git, models, and tests directories
            # Note: We exclude 'models' to prevent moving things already in models/
            # We exclude 'tests' as per best practice (don't ship test data as models unless intended)
            parts = file_path.relative_to(workspace_path).parts
            if ".git" in parts or "models" in parts or "tests" in parts:
                continue

            if self._is_model_artifact(file_path):
                files_to_move.append(file_path)

        for src in files_to_move:
            dest = distilled_dir / src.name
            if dest.exists():
                logger.warning(f"Destination {dest} already exists. Overwriting.")

            logger.info(f"Moving {src} to {dest}")
            shutil.move(str(src), str(dest))

    def _is_model_artifact(self, file_path: Path) -> bool:
        """Checks if a file matches the allow-list for model artifacts."""
        if file_path.name in self.MODEL_FILENAMES:
            return True
        if file_path.suffix in self.MODEL_EXTENSIONS:
            return True
        return False

    def _configure_lfs(self, workspace_path: Path) -> None:
        """
        Finds files > 100MB and tracks them with Git LFS.
        """
        if not self.git_lfs.is_installed():
            logger.error("Git LFS is not installed.")
            raise RuntimeError("Git LFS is not installed.")

        if not self.git_lfs.is_initialized(workspace_path):
            self.git_lfs.initialize(workspace_path)

        large_files = self.git_lfs.find_large_files(workspace_path, self.LFS_THRESHOLD)

        if large_files:
            # git lfs track takes patterns. We can pass exact relative paths.
            # We need to escape spaces if any? subprocess handles args usually.
            # But git lfs track writes to .gitattributes using the pattern provided.
            # Providing exact paths is safe.
            self.git_lfs.track_patterns(workspace_path, large_files)

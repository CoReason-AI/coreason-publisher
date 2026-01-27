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

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class PublisherConfig(BaseSettings):  # type: ignore[misc]
    """
    Configuration for the Coreason Publisher.
    Reads from environment variables and .env file.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Thresholds
    lfs_threshold_mb: int = Field(default=100, description="Threshold for Git LFS in MB")
    remote_storage_threshold_mb: int = Field(default=70 * 1024, description="Threshold for remote storage in MB")

    # Assay Service
    assay_api_url: Optional[str] = Field(default=None, description="Assay API Base URL")
    assay_api_token: Optional[SecretStr] = Field(default=None, description="Assay API Token")

    # Foundry Service
    foundry_api_url: Optional[str] = Field(default=None, description="Foundry API Base URL")
    foundry_api_token: Optional[SecretStr] = Field(default=None, description="Foundry API Token")

    # GitLab
    gitlab_url: str = Field(default="https://gitlab.com", description="GitLab Instance URL")
    gitlab_token: Optional[SecretStr] = Field(default=None, description="GitLab Private Token")
    gitlab_project_id: Optional[str] = Field(default=None, description="GitLab Project ID")

    # Server Configuration
    server_port: int = Field(default=8000, description="Server Port")
    workers: int = Field(default=1, description="Number of workers")

    @property
    def lfs_threshold_bytes(self) -> int:
        """Returns the LFS threshold in bytes."""
        return self.lfs_threshold_mb * 1024 * 1024

    @property
    def remote_storage_threshold_bytes(self) -> int:
        """Returns the remote storage threshold in bytes."""
        return self.remote_storage_threshold_mb * 1024 * 1024

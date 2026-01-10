# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_publisher

from unittest.mock import MagicMock, patch

from coreason_publisher.utils.logger import configure_logging


def test_logger_mkdir_called() -> None:
    """
    Ensure that `configure_logging()` calls mkdir() when the logs directory doesn't exist.
    """
    # Use patch context manager to patch Path in coreason_publisher.utils.logger
    # Since we are not reloading, we need to make sure we patch the object that the module uses.
    # The module does `from pathlib import Path`. So we need to patch `coreason_publisher.utils.logger.Path`.

    with patch("coreason_publisher.utils.logger.Path") as mock_path_cls:
        # Configure the mock instance returned by Path("logs")
        mock_path_instance = MagicMock()
        mock_path_cls.return_value = mock_path_instance

        # Scenario: .exists() returns False
        mock_path_instance.exists.return_value = False

        # Call the function directly
        configure_logging()

        # Verify mkdir was called
        mock_path_instance.mkdir.assert_called_with(parents=True, exist_ok=True)


def test_logger_mkdir_not_called() -> None:
    """
    Ensure that `configure_logging()` does NOT call mkdir() when the logs directory exists.
    """
    with patch("coreason_publisher.utils.logger.Path") as mock_path_cls:
        mock_path_instance = MagicMock()
        mock_path_cls.return_value = mock_path_instance

        # Scenario: .exists() returns True
        mock_path_instance.exists.return_value = True

        # Call the function directly
        configure_logging()

        # Verify mkdir was NOT called
        mock_path_instance.mkdir.assert_not_called()

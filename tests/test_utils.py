# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_publisher

import importlib
from unittest.mock import MagicMock, patch

# Import the module so we can reload it
from coreason_publisher.utils import logger


def test_logger_mkdir_called() -> None:
    """
    Ensure that `logger.py` calls mkdir() when the logs directory doesn't exist.
    """
    # We patch pathlib.Path because the module imports it directly.
    with patch("pathlib.Path") as mock_path_cls:
        # Configure the mock instance returned by Path("logs")
        mock_path_instance = MagicMock()
        mock_path_cls.return_value = mock_path_instance

        # Scenario: .exists() returns False
        mock_path_instance.exists.return_value = False

        # RELOAD the module to re-execute top-level code
        importlib.reload(logger)

        # Verify mkdir was called
        mock_path_instance.mkdir.assert_called_with(parents=True, exist_ok=True)


def test_logger_mkdir_not_called() -> None:
    """
    Ensure that `logger.py` does NOT call mkdir() when the logs directory exists.
    """
    with patch("pathlib.Path") as mock_path_cls:
        mock_path_instance = MagicMock()
        mock_path_cls.return_value = mock_path_instance

        # Scenario: .exists() returns True
        mock_path_instance.exists.return_value = True

        importlib.reload(logger)

        # Verify mkdir was NOT called
        mock_path_instance.mkdir.assert_not_called()

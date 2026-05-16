"""
Logging configuration

This file configures structured-style logging for the backend.
"""

import logging
import sys


def setup_logging():
    """
    Configure application logging.

    For now, logs are printed to stdout.

    In AWS ECS/Fargate, stdout logs are collected by CloudWatch.
    """

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s "
            "level=%(levelname)s "
            "logger=%(name)s "
            "message=%(message)s"
        ),
        handlers=[logging.StreamHandler(sys.stdout)],
    )


logger = logging.getLogger("ai-workspace")
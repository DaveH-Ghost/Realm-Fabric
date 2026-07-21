"""
Logging utilities.

Contains helpers for rich console output and file logging during simulation runs.
This replaces the need for stdlib 'logging' to avoid name conflicts.
"""

from __future__ import annotations

from campaign_rpg_engine.log_utils.logger import (
    close_file_logging as close_file_logging,
)
from campaign_rpg_engine.log_utils.logger import (
    exception_already_logged as exception_already_logged,
)
from campaign_rpg_engine.log_utils.logger import (
    log_error as log_error,
)
from campaign_rpg_engine.log_utils.logger import (
    log_turn as log_turn,
)
from campaign_rpg_engine.log_utils.logger import (
    mark_exception_logged as mark_exception_logged,
)
from campaign_rpg_engine.log_utils.logger import (
    setup_file_logging as setup_file_logging,
)

__all__ = [
    "close_file_logging",
    "exception_already_logged",
    "log_error",
    "log_turn",
    "mark_exception_logged",
    "setup_file_logging",
]

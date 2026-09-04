"""rlgen -- the shared contract every baseline in this benchmark is measured under.

Import order matters only in that `tags` and `protocol` have no internal dependencies; everything
else builds on them.
"""
from . import tags  # noqa: F401
from .protocol import Protocol, MODES, TASKS  # noqa: F401

__all__ = ["tags", "Protocol", "MODES", "TASKS"]
__version__ = "0.1.0"

"""Safety package exports."""

from .classifier import (
    apply_safety_gate,
    classify,
    is_protected_profile,
    was_dry_run_requested,
)
from .tier_table import TIER_TABLE, TIER_3_SUBSTRINGS

__all__ = [
    "apply_safety_gate",
    "classify",
    "is_protected_profile",
    "was_dry_run_requested",
    "TIER_TABLE",
    "TIER_3_SUBSTRINGS",
]

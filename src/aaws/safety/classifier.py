"""Risk classification and safety gate enforcement."""

from __future__ import annotations

import fnmatch

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from ..errors import ProtectedProfileError
from .tier_table import TIER_3_SUBSTRINGS, TIER_TABLE

console = Console()

# EC2 commands that support --dry-run (can be expanded)
_DRY_RUN_PREFIXES = (
    "aws ec2 run-instances",
    "aws ec2 terminate-instances",
    "aws ec2 start-instances",
    "aws ec2 stop-instances",
    "aws ec2 create-",
    "aws ec2 describe-",
)


# ── Classification ────────────────────────────────────────────────────────────

def classify(command: str, llm_tier: int) -> int:
    """
    Classify a command into risk tier 0–3.

    Strategy:
      1. Check TIER_3_SUBSTRINGS for catastrophic patterns.
      2. Find the longest matching prefix in TIER_TABLE.
      3. If no match, fall back to llm_tier.
    """
    cmd_lower = command.lower().strip()

    # Tier 3 composite pattern check
    for prefix, substring in TIER_3_SUBSTRINGS:
        prefix_match = (not prefix) or cmd_lower.startswith(prefix.lower())
        sub_match = (not substring) or (substring.lower() in cmd_lower)
        if prefix_match and sub_match:
            return 3

    # Longest-prefix match in TIER_TABLE
    best_tier: int | None = None
    best_len = 0
    for prefix, tier in TIER_TABLE.items():
        prefix_lower = prefix.lower()
        if cmd_lower.startswith(prefix_lower) and len(prefix_lower) > best_len:
            best_tier = tier
            best_len = len(prefix_lower)

    if best_tier is not None:
        return best_tier

    return llm_tier


# ── Profile protection ────────────────────────────────────────────────────────

def is_protected_profile(profile: str, patterns: list[str]) -> bool:
    """
    Return True if profile matches any of the given glob patterns.
    Comparison is case-insensitive.
    """
    profile_lower = profile.lower()
    for pattern in patterns:
        if fnmatch.fnmatch(profile_lower, pattern.lower()):
            return True
    return False


# ── Safety gate ───────────────────────────────────────────────────────────────

def apply_safety_gate(
    command: str,
    tier: int,
    explanation: str,
    profile: str,
    config: object,
    *,
    accept_responsibility: bool = False,
    auto_confirm: bool = False,
) -> bool:
    """
    Apply the appropriate confirmation gate for the given risk tier.

    Returns True if the command should be executed, False to cancel.
    Raises ProtectedProfileError if profile is protected and tier > 0.

    Tier behaviour:
      0 → auto-execute (no prompt)
      1 → show command + [y/n] confirm (or auto-confirm with --yes)
      2 → show warning panel + type "yes" confirm + optional --dry-run offer
          (or auto-confirm with --yes)
      3 → refuse unless accept_responsibility=True, then falls through to tier-2 flow
    """
    safety = getattr(config, "safety", None)
    auto_execute_tier: int = int(getattr(safety, "auto_execute_tier", 0))
    protected_profiles: list[str] = list(getattr(safety, "protected_profiles", []))

    # Protected profile check: block any write on protected profiles
    if tier > 0 and is_protected_profile(profile, protected_profiles):
        raise ProtectedProfileError(profile)

    # Auto-execute if tier is within the configured threshold
    if tier <= auto_execute_tier:
        return True

    # ── Tier 0: auto-execute ─────────────────────────────────────────────────
    if tier == 0:
        return True

    # Show command + explanation for all confirmation tiers
    console.print(f"\n[bold]Command:[/bold] [cyan]{command}[/cyan]")
    console.print(f"[dim]{explanation}[/dim]\n")

    # ── Tier 1: simple y/n ───────────────────────────────────────────────────
    if tier == 1:
        if auto_confirm:
            console.print("[dim]Auto-confirmed (--yes)[/dim]")
            return True
        return Confirm.ask("Run this command?")

    # ── Tier 2: warning + type "yes" ─────────────────────────────────────────
    if tier == 2:
        console.print(
            Panel(
                "[bold yellow]⚠ WARNING[/bold yellow]  This operation is "
                "[bold red]irreversible[/bold red] — it cannot be undone.",
                border_style="yellow",
                title="Destructive Operation",
            )
        )

        if auto_confirm:
            console.print("[dim]Auto-confirmed (--yes)[/dim]")
            return True

        # Offer --dry-run for EC2 commands that support it
        cmd_lower = command.lower()
        if any(cmd_lower.startswith(p.lower()) for p in _DRY_RUN_PREFIXES):
            if "--dry-run" not in cmd_lower:
                if Confirm.ask("Validate first with --dry-run (no changes will be made)?"):
                    # Signal caller to re-run with --dry-run by returning a special sentinel
                    # We use a module-level flag approach: caller checks DRY_RUN_REQUESTED
                    _set_dry_run_requested()
                    return False

        answer = Prompt.ask(
            'Type [bold]"yes"[/bold] to confirm, or press Enter to cancel',
        )
        return answer.strip().lower() == "yes"

    # ── Tier 3: refuse / override ─────────────────────────────────────────────
    if tier == 3:
        if not accept_responsibility:
            console.print(
                Panel(
                    "[bold red]⛔ REFUSED[/bold red]  This operation is catastrophic and may "
                    "permanently alter or destroy your AWS account or organisation.\n\n"
                    "If you are absolutely certain, re-run with "
                    "[bold]--i-accept-responsibility[/bold].",
                    border_style="red",
                    title="Catastrophic Operation Blocked",
                )
            )
            return False

        console.print(
            Panel(
                "[bold red]⚠ FINAL WARNING[/bold red]  You have accepted responsibility.\n"
                "This operation cannot be undone.",
                border_style="red",
                title="Override Active",
            )
        )
        answer = Prompt.ask(
            'Type [bold]"yes"[/bold] to confirm, or press Enter to cancel',
        )
        return answer.strip().lower() == "yes"

    return False


# ── Dry-run signal helper ─────────────────────────────────────────────────────
# Simple module-level sentinel so the CLI layer can detect when the user chose
# --dry-run from the confirmation prompt.

_dry_run_requested = False


def _set_dry_run_requested() -> None:
    global _dry_run_requested  # noqa: PLW0603
    _dry_run_requested = True


def was_dry_run_requested() -> bool:
    global _dry_run_requested  # noqa: PLW0603
    val = _dry_run_requested
    _dry_run_requested = False  # reset after read
    return val

"""Interactive REPL session with in-process conversation history."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel

console = Console()


def run_session(config: object, profile: str, region: str) -> None:
    """
    Start an interactive aaws REPL.

    Maintains conversation history in-process (never written to disk).
    History is bounded to the last 10 exchanges to keep LLM context manageable.
    """
    import time as _time  # noqa: PLC0415

    from .audit import AuditConfig, AuditEntry, append as audit_append  # noqa: PLC0415
    from .errors import (  # noqa: PLC0415
        AawsError,
        ProtectedProfileError,
        TranslationError,
        handle_error,
    )
    from .executor import execute  # noqa: PLC0415
    from .formatter import format_output  # noqa: PLC0415
    from .providers import get_provider  # noqa: PLC0415
    from .safety.classifier import apply_safety_gate, classify  # noqa: PLC0415
    from .translator import translate  # noqa: PLC0415

    from .rate_limit import RateLimiter  # noqa: PLC0415

    provider = get_provider(config)

    # Rate limiter
    session_cfg = getattr(config, "session", None)
    rl_cfg = getattr(session_cfg, "rate_limit", None) if session_cfg else None
    rate_limiter = RateLimiter(
        max_per_minute=getattr(rl_cfg, "max_per_minute", 20) if rl_cfg else 20,
        burst=getattr(rl_cfg, "burst", 5) if rl_cfg else 5,
        enabled=getattr(rl_cfg, "enabled", True) if rl_cfg else True,
    )

    audit_cfg_section = getattr(config, "audit", None)
    audit_cfg = AuditConfig(
        enabled=getattr(audit_cfg_section, "enabled", True) if audit_cfg_section else True,
        path=getattr(audit_cfg_section, "path", None) if audit_cfg_section else None,
        max_size_mb=getattr(audit_cfg_section, "max_size_mb", 10) if audit_cfg_section else 10,
    )
    history: list[dict[str, str]] = []

    # ── Session header ────────────────────────────────────────────────────────
    console.print(
        Panel(
            f"[bold]Profile:[/bold] {profile}  "
            f"[bold]Region:[/bold] {region}\n"
            "[dim]Type 'exit' or 'quit' to end the session. Ctrl+C to abort.[/dim]",
            title="[bold cyan]aaws interactive session[/bold cyan]",
            border_style="cyan",
        )
    )

    # ── REPL loop ─────────────────────────────────────────────────────────────
    while True:
        try:
            user_input = console.input("[bold cyan]\\[aaws][/bold cyan]> ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye.[/dim]")
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit"):
            console.print("[dim]Goodbye.[/dim]")
            break

        # Rate-limit check
        allowed, retry_after = rate_limiter.try_acquire()
        if not allowed:
            console.print(
                f"[bold yellow]Rate limited.[/bold yellow] "
                f"Try again in {retry_after:.0f}s."
            )
            continue

        # Translate NL → command (pass bounded history)
        try:
            response = translate(
                user_input,
                profile,
                region,
                history[-10:],
                provider,
            )
        except TranslationError as e:
            console.print(f"[bold red]Translation failed:[/bold red] {e}")
            continue
        except AawsError as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            continue

        # Handle clarification request
        if response.clarification:
            console.print(f"[bold yellow]?[/bold yellow] {response.clarification}")
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": response.clarification})
            continue

        # Safety gate
        tier = classify(response.command, response.risk_tier)
        try:
            should_run = apply_safety_gate(
                response.command,
                tier,
                response.explanation,
                profile,
                config,
            )
        except ProtectedProfileError as e:
            console.print(f"[bold red]Blocked:[/bold red] {e}")
            continue

        if not should_run:
            console.print("[dim]Cancelled.[/dim]")
            continue

        # Execute with audit
        start = _time.monotonic()
        exit_code = 0
        try:
            result = execute(response.command)
            exit_code = result.exit_code
        except KeyboardInterrupt:
            exit_code = -2
            raise
        except Exception:
            exit_code = -1
            raise
        finally:
            if audit_cfg.enabled:
                duration_ms = int((_time.monotonic() - start) * 1000)
                audit_append(
                    AuditEntry(
                        command=response.command,
                        tier=tier,
                        profile=profile,
                        region=region,
                        exit_code=exit_code,
                        success=exit_code == 0,
                        mode="session",
                        duration_ms=duration_ms,
                    ),
                    audit_cfg,
                )

        # Update history — include execution output so the LLM can resolve
        # follow-up references like "show details about the first one"
        history.append({"role": "user", "content": user_input})
        assistant_content = f"Command: {response.command}\n{response.explanation}"
        if result.success and result.stdout:
            # Truncate large outputs to keep history context manageable
            output_preview = result.stdout[:2000]
            if len(result.stdout) > 2000:
                output_preview += "\n... (truncated)"
            assistant_content += f"\nOutput:\n{output_preview}"
        elif not result.success and result.stderr:
            assistant_content += f"\nError: {result.stderr[:500]}"
        history.append({"role": "assistant", "content": assistant_content})

        # Render output
        if result.success:
            format_output(result.stdout, raw=getattr(getattr(config, "output", None), "raw", False))
        else:
            handle_error(response.command, result, profile, provider)

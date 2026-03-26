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

    provider = get_provider(config)
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

        # Execute
        result = execute(response.command)

        # Update history
        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": response.command})

        # Render output
        if result.success:
            format_output(result.stdout, raw=getattr(getattr(config, "output", None), "raw", False))
        else:
            handle_error(response.command, result, profile, provider)

"""aaws CLI — entry point for all commands."""

from __future__ import annotations

from typing import Annotated, Optional

import typer
from rich.console import Console

app = typer.Typer(
    name="aaws",
    help="AI-assisted AWS CLI — natural language in, aws command out.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

config_app = typer.Typer(help="Manage aaws configuration.")
app.add_typer(config_app, name="config")

console = Console()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resolve_aws_context(
    profile: str | None,
    region: str | None,
    config: object,
) -> tuple[str, str]:
    """Return the effective AWS profile and region."""
    import boto3  # noqa: PLC0415

    aws = getattr(config, "aws", None)
    effective_profile = profile or getattr(aws, "default_profile", None) or "default"

    if region:
        effective_region = region
    elif getattr(aws, "default_region", None):
        effective_region = aws.default_region  # type: ignore[union-attr]
    else:
        try:
            session = boto3.Session(profile_name=effective_profile)
            effective_region = session.region_name or "us-east-1"
        except Exception:
            effective_region = "us-east-1"

    return effective_profile, effective_region


def _load_or_exit() -> object:
    """Load config or print actionable error and exit."""
    from .config import load_config  # noqa: PLC0415
    from .errors import ConfigNotFoundError  # noqa: PLC0415

    try:
        return load_config()
    except ConfigNotFoundError:
        console.print(
            "[bold red]No configuration found.[/bold red] "
            "Run [cyan]aaws config init[/cyan] to set up."
        )
        raise typer.Exit(1)


# ── Root command ──────────────────────────────────────────────────────────────

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    request: Annotated[
        Optional[str], typer.Argument(help="Natural language AWS request")
    ] = None,
    profile: Annotated[
        Optional[str], typer.Option("--profile", "-p", help="AWS profile to use")
    ] = None,
    region: Annotated[
        Optional[str], typer.Option("--region", "-r", help="AWS region to use")
    ] = None,
    raw: Annotated[
        bool, typer.Option("--raw", help="Print raw JSON without formatting")
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show generated command without executing it")
    ] = False,
    accept_responsibility: Annotated[
        bool,
        typer.Option(
            "--i-accept-responsibility",
            help="Override tier-3 (catastrophic) operation refusal",
        ),
    ] = False,
) -> None:
    """Translate a natural language request into an AWS CLI command and run it."""
    if ctx.invoked_subcommand is not None:
        return

    if request is None:
        console.print(
            "Usage: aaws [OPTIONS] REQUEST\n\nRun [cyan]aaws --help[/cyan] for more information."
        )
        raise typer.Exit()

    from .errors import AawsError, ProtectedProfileError, TranslationError, handle_error  # noqa: PLC0415
    from .executor import check_aws_cli, execute  # noqa: PLC0415
    from .formatter import format_output  # noqa: PLC0415
    from .providers import get_provider  # noqa: PLC0415
    from .safety.classifier import apply_safety_gate, classify, was_dry_run_requested  # noqa: PLC0415
    from .translator import translate  # noqa: PLC0415

    check_aws_cli()
    config = _load_or_exit()
    effective_profile, effective_region = _resolve_aws_context(profile, region, config)
    effective_raw = raw or getattr(getattr(config, "output", None), "raw", False)

    provider = get_provider(config)

    # Translate
    try:
        response = translate(request, effective_profile, effective_region, [], provider)
    except TranslationError as e:
        console.print(f"[bold red]Translation failed:[/bold red] {e}")
        raise typer.Exit(1)
    except AawsError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)

    # Handle clarification
    if response.clarification:
        console.print(f"[bold yellow]?[/bold yellow] {response.clarification}")
        raise typer.Exit()

    tier = classify(response.command, response.risk_tier)

    # Dry-run flag: show command; don't execute
    if dry_run:
        console.print(f"\n[bold]Generated command:[/bold] [cyan]{response.command}[/cyan]")
        console.print(f"[dim]{response.explanation}[/dim]")
        console.print(f"[dim]Risk tier: {tier}[/dim]")
        raise typer.Exit()

    # Safety gate
    try:
        should_run = apply_safety_gate(
            response.command,
            tier,
            response.explanation,
            effective_profile,
            config,
            accept_responsibility=accept_responsibility,
        )
    except ProtectedProfileError as e:
        console.print(f"[bold red]Blocked:[/bold red] {e}")
        raise typer.Exit(1)

    if was_dry_run_requested():
        # User chose --dry-run from the confirmation prompt — re-run with --dry-run appended
        dry_command = response.command + " --dry-run"
        console.print(f"\n[bold]Running:[/bold] [cyan]{dry_command}[/cyan]")
        result = execute(dry_command)
        if result.success:
            console.print("[green]Dry run succeeded — no changes were made.[/green]")
            console.print(result.stdout or "")
        else:
            handle_error(dry_command, result, effective_profile, provider)
        raise typer.Exit()

    if not should_run:
        console.print("[dim]Cancelled.[/dim]")
        raise typer.Exit()

    result = execute(response.command)
    if result.success:
        format_output(result.stdout, raw=effective_raw)
    else:
        handle_error(response.command, result, effective_profile, provider)
        raise typer.Exit(result.exit_code)


# ── explain command ───────────────────────────────────────────────────────────

@app.command("explain")
def explain_command(
    command: Annotated[str, typer.Argument(help="AWS CLI command to explain")],
) -> None:
    """Explain what an existing AWS CLI command does."""
    from .errors import AawsError  # noqa: PLC0415
    from .providers import get_provider  # noqa: PLC0415
    from .providers.base import Message, TOOL_SCHEMA  # noqa: PLC0415

    config = _load_or_exit()
    provider = get_provider(config)

    messages = [
        Message(
            role="user",
            content=(
                f"Explain the following AWS CLI command in plain English. "
                f"Describe what it does, what each flag means, and any important "
                f"safety considerations or caveats:\n\n  {command}"
            ),
        )
    ]

    try:
        response = provider.complete(messages, TOOL_SCHEMA)
        console.print(f"\n[bold]Command:[/bold] [cyan]{command}[/cyan]\n")
        console.print(response.explanation or "No explanation available.")
    except AawsError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)


# ── session command ───────────────────────────────────────────────────────────

@app.command("session")
def session_command(
    profile: Annotated[
        Optional[str], typer.Option("--profile", "-p", help="AWS profile to use")
    ] = None,
    region: Annotated[
        Optional[str], typer.Option("--region", "-r", help="AWS region to use")
    ] = None,
) -> None:
    """Start an interactive session with conversation context."""
    from .executor import check_aws_cli  # noqa: PLC0415
    from .session import run_session  # noqa: PLC0415

    check_aws_cli()
    config = _load_or_exit()
    effective_profile, effective_region = _resolve_aws_context(profile, region, config)
    run_session(config, effective_profile, effective_region)


# ── config commands ───────────────────────────────────────────────────────────

@config_app.command("init")
def config_init() -> None:
    """Run the first-time configuration wizard."""
    from rich.prompt import Confirm, Prompt  # noqa: PLC0415

    from .config import AawsConfig, LLMConfig, write_config  # noqa: PLC0415

    console.print("[bold cyan]aaws configuration wizard[/bold cyan]\n")

    provider_choice = Prompt.ask(
        "LLM provider",
        choices=["bedrock", "openai"],
        default="bedrock",
    )

    if provider_choice == "bedrock":
        model = Prompt.ask(
            "Bedrock model ID",
            default="anthropic.claude-3-5-haiku-20241022-v1:0",
        )
        api_key = None
    else:
        model = Prompt.ask("OpenAI model", default="gpt-4o-mini")
        api_key = Prompt.ask(
            "OpenAI API key (or set OPENAI_API_KEY env var)",
            password=True,
        )

    default_profile = Prompt.ask("Default AWS profile", default="default")
    default_region = Prompt.ask("Default AWS region", default="us-east-1")

    from .config import AWSConfig  # noqa: PLC0415

    config = AawsConfig(
        llm=LLMConfig(provider=provider_choice, model=model, api_key=api_key or None),
        aws=AWSConfig(default_profile=default_profile, default_region=default_region),
    )
    path = write_config(config)
    console.print(f"\n[green]✓[/green] Configuration saved to [cyan]{path}[/cyan]")
    console.print('Run [cyan]aaws "list my S3 buckets"[/cyan] to test.')


@config_app.command("show")
def config_show() -> None:
    """Show the resolved effective configuration (secrets masked)."""
    import json  # noqa: PLC0415

    config = _load_or_exit()
    data = config.model_dump()  # type: ignore[union-attr]

    # Mask sensitive fields
    if data.get("llm", {}).get("api_key"):
        data["llm"]["api_key"] = "***"

    console.print_json(json.dumps(data, indent=2))

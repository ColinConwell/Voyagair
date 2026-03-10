"""CLI command: AI-assisted interactive exploration of travel options."""

from __future__ import annotations

import asyncio
from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

app = typer.Typer(invoke_without_command=True)
console = Console()


@app.command()
def explore(
    prompt: Optional[str] = typer.Argument(
        None,
        help="Describe your travel scenario (or omit for interactive mode)",
    ),
    model: str = typer.Option("gpt-5.4", "--model", "-m", help="LLM model to use"),
    provider: str = typer.Option("openai", "--provider", help="LLM provider: openai, anthropic, ollama"),
) -> None:
    """AI-assisted interactive exploration of travel options.

    Describe your travel scenario and the AI agent will help you search for flights,
    compare routes, and build itineraries using all available data sources.
    """
    asyncio.run(_run_explore(prompt, model, provider))


async def _run_explore(prompt: str | None, model: str, provider: str) -> None:
    try:
        from voyagair.api.agent.agent import TravelAgent
    except ImportError as e:
        console.print(f"[red]AI agent requires litellm. Install with: pip install litellm[/red]")
        return

    agent = TravelAgent(model=model, provider=provider)

    if prompt:
        with console.status("[bold]Thinking...", spinner="dots"):
            response = await agent.chat(prompt)
        console.print(Panel(Markdown(response), title="Voyagair AI", border_style="cyan"))
        return

    console.print(Panel(
        "Welcome to Voyagair AI Explorer.\n"
        "Describe your travel scenario and I'll help you find the best options.\n"
        "Type 'quit' or 'exit' to leave.",
        title="Voyagair AI",
        border_style="cyan",
    ))

    while True:
        try:
            user_input = console.input("[bold cyan]You:[/bold cyan] ")
        except (EOFError, KeyboardInterrupt):
            break

        if user_input.strip().lower() in ("quit", "exit", "q"):
            console.print("[dim]Goodbye![/dim]")
            break

        if not user_input.strip():
            continue

        with console.status("[bold]Thinking...", spinner="dots"):
            response = await agent.chat(user_input)
        console.print(Panel(Markdown(response), title="Voyagair AI", border_style="cyan"))

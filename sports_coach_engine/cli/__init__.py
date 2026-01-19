"""
Sports Coach Engine CLI - Main entry point.

Provides a command-line interface for Claude Code to interact with the
Sports Coach Engine. All commands return structured JSON for easy parsing.

Usage:
    sce init                        # Initialize data directories
    sce sync                        # Import activities from Strava
    sce status                      # Get current training metrics
    sce today                       # Get today's workout
    sce vdot calculate              # Calculate VDOT from race performance
    sce vdot paces                  # Generate training pace zones
    sce guardrails quality-volume   # Validate T/I/R pace volumes
    sce guardrails break-return     # Plan return after training break
"""

from pathlib import Path
from typing import Optional

import typer

# Create the main Typer app
app = typer.Typer(
    name="sce",
    help="Sports Coach Engine - AI-powered adaptive running coach (JSON output)",
    add_completion=False,  # Keep it simple for v0
    no_args_is_help=True,
)


# Global context shared across commands
class CLIContext:
    """Context object passed to all CLI commands.

    Attributes:
        repo_root: Repository root path (auto-detected or specified)
    """

    def __init__(self, repo_root: Optional[Path] = None):
        self.repo_root = repo_root


@app.callback()
def main(
    ctx: typer.Context,
    repo_root: Optional[Path] = typer.Option(
        None,
        "--repo-root",
        help="Repository root path (auto-detected if not specified)",
    ),
) -> None:
    """Sports Coach Engine CLI - All commands output JSON."""
    # Create context object
    ctx.obj = CLIContext(repo_root=repo_root)


# Import and register commands
from sports_coach_engine.cli.commands import auth, metrics, plan, profile, vdot, guardrails, analysis, validation, memory, activity, race
from sports_coach_engine.cli.commands.goal import goal_set_command
from sports_coach_engine.cli.commands.init_cmd import init_command
from sports_coach_engine.cli.commands.status import status_command
from sports_coach_engine.cli.commands.sync import sync_command
from sports_coach_engine.cli.commands.today import today_command
from sports_coach_engine.cli.commands.week import week_command

# Register commands
app.command(name="init", help="Initialize data directories and config")(init_command)
app.command(name="sync", help="Import activities from Strava")(sync_command)
app.command(name="status", help="Get current training metrics")(status_command)
app.command(name="today", help="Get today's workout recommendation")(today_command)
app.command(name="week", help="Get weekly training summary")(week_command)
app.command(name="goal", help="Set a race goal")(goal_set_command)

# Register subcommands
app.add_typer(auth.app, name="auth", help="Manage Strava authentication")
app.add_typer(metrics.app, name="metrics", help="Manage training metrics")
app.add_typer(plan.app, name="plan", help="Manage training plans")
app.add_typer(profile.app, name="profile", help="Manage athlete profile")
app.add_typer(vdot.app, name="vdot", help="VDOT calculations and training paces")
app.add_typer(guardrails.app, name="guardrails", help="Volume validation and recovery planning")
app.add_typer(analysis.app, name="analysis", help="Weekly analysis and risk assessment")
app.add_typer(analysis.risk_app, name="risk", help="Risk assessment commands")
app.add_typer(validation.app, name="validation", help="Interval/plan structure validation and goal feasibility")
app.add_typer(memory.app, name="memory", help="Manage athlete memories and insights")
app.add_typer(activity.app, name="activity", help="List and search activities")
app.add_typer(race.app, name="race", help="Race performance tracking and PB management")

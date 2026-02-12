"""
resilio auth - Manage Strava authentication.

Handle OAuth flow for Strava API access: generate URL, exchange code, check status.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
import yaml

from resilio.core.config import load_config
from resilio.core.strava import (
    StravaAuthError,
    exchange_code_for_tokens,
    initiate_oauth,
)
from resilio.cli.errors import EXIT_AUTH_FAILURE, EXIT_CONFIG_MISSING, EXIT_SUCCESS
from resilio.cli.output import create_error_envelope, create_success_envelope, output_json

# Create subcommand app
app = typer.Typer(help="Manage Strava authentication")


@app.command(name="url")
def auth_url_command(ctx: typer.Context) -> None:
    """Generate Strava OAuth authorization URL.

    Returns the URL for the athlete to open in their browser to authorize
    the app to access their Strava data.

    Workflow:
        1. Run: resilio auth url
        2. Open the URL in browser
        3. Authorize the app
        4. Copy the authorization code from redirect URL
        5. Run: resilio auth exchange --code YOUR_CODE
    """
    # Get repo root
    cli_ctx = ctx.obj
    repo_root = cli_ctx.repo_root or Path.cwd()

    # Load config
    try:
        config = load_config(repo_root)
    except Exception as e:
        envelope = create_error_envelope(
            error_type="config",
            message=f"Failed to load config: {e}",
            data={"next_steps": "Run: resilio init to create config files"},
        )
        output_json(envelope)
        raise typer.Exit(code=EXIT_CONFIG_MISSING)

    # Get client_id from secrets
    secrets_path = repo_root / "config" / "secrets.local.yaml"
    try:
        with open(secrets_path) as f:
            secrets = yaml.safe_load(f)
        client_id = secrets.get("strava", {}).get("client_id")

        if not client_id or client_id == "YOUR_CLIENT_ID":
            envelope = create_error_envelope(
                error_type="config",
                message="Strava client_id not configured in config/secrets.local.yaml",
                data={
                    "next_steps": "Edit config/secrets.local.yaml and add your Strava client_id"
                },
            )
            output_json(envelope)
            raise typer.Exit(code=EXIT_CONFIG_MISSING)

    except FileNotFoundError:
        envelope = create_error_envelope(
            error_type="config",
            message="secrets.local.yaml not found",
            data={"next_steps": "Run: resilio init to create config files"},
        )
        output_json(envelope)
        raise typer.Exit(code=EXIT_CONFIG_MISSING)

    # Generate OAuth URL
    redirect_uri = "http://localhost"
    auth_url = initiate_oauth(client_id, redirect_uri)

    # Return success envelope
    envelope = create_success_envelope(
        message="Generated Strava OAuth authorization URL",
        data={
            "url": auth_url,
            "redirect_uri": redirect_uri,
            "scopes": ["activity:read_all", "profile:read_all"],
            "instructions": [
                "1. Open the URL in your browser",
                "2. Authorize the app",
                "3. Copy the 'code' parameter from redirect URL",
                "4. Run: resilio auth exchange --code YOUR_CODE",
            ],
        },
    )
    output_json(envelope)
    raise typer.Exit(code=EXIT_SUCCESS)


@app.command(name="exchange")
def auth_exchange_command(
    ctx: typer.Context,
    code: str = typer.Option(..., "--code", help="Authorization code from Strava redirect"),
) -> None:
    """Exchange authorization code for access tokens.

    Takes the authorization code from Strava OAuth redirect and exchanges it
    for access and refresh tokens, which are stored in config/secrets.local.yaml.

    Args:
        code: Authorization code from redirect URL (after authorizing in browser)
    """
    # Get repo root
    cli_ctx = ctx.obj
    repo_root = cli_ctx.repo_root or Path.cwd()

    # Load config
    try:
        config = load_config(repo_root)
    except Exception as e:
        envelope = create_error_envelope(
            error_type="config",
            message=f"Failed to load config: {e}",
            data={"next_steps": "Run: resilio init to create config files"},
        )
        output_json(envelope)
        raise typer.Exit(code=EXIT_CONFIG_MISSING)

    # Load secrets
    secrets_path = repo_root / "config" / "secrets.local.yaml"
    try:
        with open(secrets_path) as f:
            secrets = yaml.safe_load(f)

        client_id = secrets.get("strava", {}).get("client_id")
        client_secret = secrets.get("strava", {}).get("client_secret")

        if not client_id or client_id == "YOUR_CLIENT_ID":
            envelope = create_error_envelope(
                error_type="config",
                message="Strava client_id not configured",
                data={
                    "next_steps": "Edit config/secrets.local.yaml and add your Strava credentials"
                },
            )
            output_json(envelope)
            raise typer.Exit(code=EXIT_CONFIG_MISSING)

        if not client_secret or client_secret == "YOUR_CLIENT_SECRET":
            envelope = create_error_envelope(
                error_type="config",
                message="Strava client_secret not configured",
                data={
                    "next_steps": "Edit config/secrets.local.yaml and add your Strava credentials"
                },
            )
            output_json(envelope)
            raise typer.Exit(code=EXIT_CONFIG_MISSING)

    except FileNotFoundError:
        envelope = create_error_envelope(
            error_type="config",
            message="secrets.local.yaml not found",
            data={"next_steps": "Run: resilio init to create config files"},
        )
        output_json(envelope)
        raise typer.Exit(code=EXIT_CONFIG_MISSING)

    # Exchange code for tokens
    try:
        tokens = exchange_code_for_tokens(client_id, client_secret, code)
    except StravaAuthError as e:
        envelope = create_error_envelope(
            error_type="auth",
            message=f"Token exchange failed: {e}",
            data={
                "next_steps": "Run: resilio auth url to get a new authorization URL and try again"
            },
        )
        output_json(envelope)
        raise typer.Exit(code=EXIT_AUTH_FAILURE)

    # Update secrets file with tokens
    secrets["strava"]["access_token"] = tokens["access_token"]
    secrets["strava"]["refresh_token"] = tokens["refresh_token"]
    secrets["strava"]["token_expires_at"] = tokens["expires_at"]

    with open(secrets_path, "w") as f:
        yaml.safe_dump(secrets, f, default_flow_style=False)

    # Return success envelope (with tokens redacted)
    expires_dt = datetime.fromtimestamp(tokens["expires_at"])
    envelope = create_success_envelope(
        message="Successfully authenticated with Strava",
        data={
            "status": "authorized",
            "expires_at": expires_dt.isoformat(),
            "token_stored": str(secrets_path),
            "next_steps": ["Run: resilio sync to import your activities"],
        },
    )
    output_json(envelope)
    raise typer.Exit(code=EXIT_SUCCESS)


@app.command(name="status")
def auth_status_command(ctx: typer.Context) -> None:
    """Check Strava token status.

    Checks whether access token exists and whether it's expired.
    """
    # Get repo root
    cli_ctx = ctx.obj
    repo_root = cli_ctx.repo_root or Path.cwd()

    # Load secrets
    secrets_path = repo_root / "config" / "secrets.local.yaml"
    try:
        with open(secrets_path) as f:
            secrets = yaml.safe_load(f)

        access_token = secrets.get("strava", {}).get("access_token")
        expires_at = secrets.get("strava", {}).get("token_expires_at")

        # Check if token exists
        if not access_token:
            envelope = create_error_envelope(
                error_type="auth",
                message="No Strava token found",
                data={
                    "authenticated": False,
                    "next_steps": "Run: resilio auth url to start OAuth flow",
                },
            )
            output_json(envelope)
            raise typer.Exit(code=EXIT_AUTH_FAILURE)

        # Check if token is expired
        if expires_at:
            expires_dt = datetime.fromtimestamp(expires_at)
            now = datetime.now()
            is_expired = now >= expires_dt

            if is_expired:
                envelope = create_error_envelope(
                    error_type="auth",
                    message=f"Strava token expired on {expires_dt.isoformat()}",
                    data={
                        "authenticated": False,
                        "expired": True,
                        "expired_at": expires_dt.isoformat(),
                        "next_steps": "Run: resilio auth url to refresh authentication",
                    },
                )
                output_json(envelope)
                raise typer.Exit(code=EXIT_AUTH_FAILURE)

            # Token is valid
            envelope = create_success_envelope(
                message="Strava authentication is valid",
                data={
                    "authenticated": True,
                    "expires_at": expires_dt.isoformat(),
                    "expires_in_hours": int((expires_dt - now).total_seconds() / 3600),
                },
            )
            output_json(envelope)
            raise typer.Exit(code=EXIT_SUCCESS)

        else:
            # Token exists but no expiration info
            envelope = create_success_envelope(
                message="Strava token exists (expiration unknown)",
                data={
                    "authenticated": True,
                    "expires_at": None,
                },
            )
            output_json(envelope)
            raise typer.Exit(code=EXIT_SUCCESS)

    except FileNotFoundError:
        envelope = create_error_envelope(
            error_type="config",
            message="secrets.local.yaml not found",
            data={"next_steps": "Run: resilio init to create config files"},
        )
        output_json(envelope)
        raise typer.Exit(code=EXIT_CONFIG_MISSING)

"""
Initialize data directory structure.

Run this once to set up the local data directory with proper structure
and template files.
"""

import shutil
from pathlib import Path


def init_data_directory(root_path: Path = Path(".")):
    """Create data directory structure with templates."""

    print("Initializing Sports Coach Engine data directory...")
    print()

    # Create directory structure
    directories = [
        root_path / "config",
        root_path / "athlete",
        root_path / "activities",
        root_path / "metrics" / "daily",
        root_path / "metrics" / "weekly",
        root_path / "plans" / "archive",
        root_path / "plans" / "workouts",
        root_path / "conversations",
        root_path / "backup",
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        print(f"✓ Created: {directory}")

    print()

    # Copy template configs
    config_dir = root_path / "config"

    # Copy settings.yaml template
    settings_template = Path("templates") / "settings.yaml"
    if settings_template.exists():
        shutil.copy(settings_template, config_dir / "settings.yaml")
        print(f"✓ Created: {config_dir / 'settings.yaml'}")
    else:
        print(f"⚠ Warning: Template not found at {settings_template}")

    # Create secrets template (if doesn't exist)
    secrets_file = config_dir / "secrets.local.yaml"
    if not secrets_file.exists():
        secrets_template = Path("templates") / "secrets.local.yaml"
        if secrets_template.exists():
            shutil.copy(secrets_template, secrets_file)
            print(f"✓ Created: {secrets_file}")
        else:
            # Fallback: create inline
            secrets_file.write_text("""# DO NOT COMMIT THIS FILE
# Add to .gitignore immediately

_schema:
  format_version: "1.0.0"
  schema_type: "secrets"

strava:
  client_id: "YOUR_CLIENT_ID"
  client_secret: "YOUR_CLIENT_SECRET"
  access_token: null
  refresh_token: null
  token_expires_at: null
""")
            print(f"✓ Created: {secrets_file}")
    else:
        print(f"ℹ Already exists: {secrets_file}")

    print()
    print("✅ Data directory initialized successfully!")
    print()
    print("Next steps:")
    print("1. Edit config/secrets.local.yaml with your Strava credentials")
    print("2. Run: python -m sports_coach_engine.strava_connect (when implemented)")
    print()


if __name__ == "__main__":
    init_data_directory()

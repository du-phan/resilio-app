"""Compatibility entry point for the idempotent CLI initializer."""

from pathlib import Path


def init_data_directory(root_path: Path = Path(".")) -> None:
    """Create the provider-neutral local directory skeleton."""
    for relative in [
        "config",
        "data/athlete",
        "data/activities",
        "data/metrics/daily",
        "data/metrics/weekly",
        "data/plans/archive",
        "data/state",
    ]:
        (root_path / relative).mkdir(parents=True, exist_ok=True)

    environment_file = root_path / ".env.local"
    if not environment_file.exists():
        environment_file.write_text(
            "# DO NOT COMMIT THIS FILE\n"
            "INTERVALS_ICU_API_KEY=\n"
        )
        environment_file.chmod(0o600)

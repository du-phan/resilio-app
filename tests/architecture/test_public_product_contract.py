"""Public release facts shared with the Resilio website."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from resilio import __version__

REPO_ROOT = Path(__file__).resolve().parents[2]
PUBLIC_PRODUCT_DOC = REPO_ROOT / "docs/product/website/README.md"
PUBLIC_EXAMPLE = REPO_ROOT / "docs/product/website/coaching-decision.example.json"


def test_release_version_is_consistent() -> None:
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())

    assert project["project"]["version"] == "0.3.0"
    assert __version__ == "0.3.0"


def test_public_product_document_matches_the_runtime_boundary() -> None:
    content = PUBLIC_PRODUCT_DOC.read_text()
    normalized = content.casefold()

    for required in (
        "ai-assisted running coach for multi-sport athletes",
        "intervals.icu",
        "athlete-managed",
        "macos",
        "athlete approval",
    ):
        assert required in normalized

    for retired_claim in (
        "total training load",
        "systemic + lower-body",
        "run and cycling workouts",
        "macos, linux",
    ):
        assert retired_claim not in normalized


def test_public_coaching_example_is_synthetic_unit_explicit_and_safe() -> None:
    payload = json.loads(PUBLIC_EXAMPLE.read_text())

    assert payload["metadata"]["synthetic"] is True
    assert payload["metadata"]["source_release"] == "v0.3.0"
    assert payload["synchronized_facts"]["running_distance_km"] >= 0
    assert payload["synchronized_facts"]["climbing_duration_minutes"] >= 0
    assert payload["missing_or_partial_evidence"]
    assert payload["coaching_judgment"]
    assert payload["proposed_action"]["requires_athlete_approval"] is True

    serialized = json.dumps(payload).casefold()
    for retired_metric in (
        "composite_readiness",
        "injury_probability",
        "systemic_load",
        "lower_body_load",
        "acwr",
    ):
        assert retired_metric not in serialized

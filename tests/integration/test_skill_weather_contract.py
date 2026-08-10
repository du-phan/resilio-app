"""Contract checks to ensure skills reference weather-aware planning flow correctly.

These tests verify:
1. Required CLI command and section presence (basic contract).
2. Philosophy alignment: weather is advisory-only (no enumerated adaptation categories,
   no coaching recommendations in the template, coach agency is preserved).
3. Consistency between .agents/ and .claude/ skill trees.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text()


def test_weekly_plan_skill_mentions_weather_cli_in_both_trees():
    agent_skill = _read(".agents/skills/weekly-plan-generate/SKILL.md")
    claude_skill = _read(".claude/skills/weekly-plan-generate/SKILL.md")

    assert "resilio weather week --start <WEEK_START>" in agent_skill
    assert "resilio weather week --start <WEEK_START>" in claude_skill
    assert "Weather Context & Adjustments" in agent_skill
    assert "Weather Context & Adjustments" in claude_skill


def test_first_session_skill_mentions_weather_location_capture():
    agent_skill = _read(".agents/skills/first-session/SKILL.md")
    claude_skill = _read(".claude/skills/first-session/SKILL.md")

    assert "Where do you usually train?" in agent_skill
    assert "Where do you usually train?" in claude_skill
    assert "--weather-location" in agent_skill
    assert "--weather-location" in claude_skill


def test_weekly_plan_skill_weather_is_non_blocking():
    """The skill must continue planning even when weather fails — weather is advisory-only."""
    for path in [
        ".agents/skills/weekly-plan-generate/SKILL.md",
        ".claude/skills/weekly-plan-generate/SKILL.md",
    ]:
        content = _read(path)
        assert (
            "weather lookup fails" in content or "weather data unavailable" in content
        ), f"{path}: must document graceful weather failure handling"


def test_weekly_plan_skill_does_not_enumerate_adaptation_categories():
    """Skill must not pre-structure adaptation categories (that narrows coach agency).

    High-freedom framing: present raw signals, trust the coach to decide.
    Medium-freedom enumeration ('time-of-day shift, indoor alternative, easy/quality swap')
    was removed as part of the advisory-only philosophy enforcement.
    """
    prohibited_phrases = [
        "time-of-day shift",
        "indoor alternative",
        "easy/quality swap",
        "Suggested adaptations",
    ]
    for path in [
        ".agents/skills/weekly-plan-generate/SKILL.md",
        ".claude/skills/weekly-plan-generate/SKILL.md",
    ]:
        content = _read(path)
        for phrase in prohibited_phrases:
            assert phrase not in content, (
                f"{path}: found '{phrase}' — this pre-structures adaptation categories and "
                "narrows coach agency. Use high-freedom framing instead."
            )


def test_weekly_plan_skill_weather_trees_are_in_sync():
    """Both skill tree copies must have the same weather section content."""
    agent_skill = _read(".agents/skills/weekly-plan-generate/SKILL.md")
    claude_skill = _read(".claude/skills/weekly-plan-generate/SKILL.md")

    # Extract weather section from each (between the section header and next **)
    def _extract_weather_section(text: str) -> str:
        lines = text.splitlines()
        in_section = False
        section_lines: list[str] = []
        for line in lines:
            if "**Weather Context & Adjustments**" in line:
                in_section = True
            elif in_section and line.startswith("**") and "Weather" not in line:
                break
            if in_section:
                section_lines.append(line)
        return "\n".join(section_lines)

    assert _extract_weather_section(agent_skill) == _extract_weather_section(claude_skill), (
        "Weather sections differ between .agents/ and .claude/ skill trees. "
        "Ensure both are updated together."
    )


def test_weekly_plan_skill_scopes_weather_to_prescribed_running():
    """Weather decisions must not turn athlete-managed sports into prescriptions."""
    for path in [
        ".agents/skills/weekly-plan-generate/SKILL.md",
        ".claude/skills/weekly-plan-generate/SKILL.md",
    ]:
        content = _read(path)
        assert "Weather informs only the running sessions prescribed" in content
        assert "Do not emit a non-running workout" in content


def test_first_session_skill_explains_why_location_matters_to_athlete():
    """Skill must tell the athlete WHY their location is being collected."""
    for path in [
        ".agents/skills/first-session/SKILL.md",
        ".claude/skills/first-session/SKILL.md",
    ]:
        content = _read(path)
        # Should mention weather context to the athlete, not just "for geocoding"
        assert (
            "weather context" in content or "heat" in content or "wind" in content
        ), f"{path}: must explain to athlete why location is collected (weather context)"

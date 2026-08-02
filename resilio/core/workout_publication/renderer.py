"""Deterministic native workout-text rendering."""

from __future__ import annotations

from resilio.schemas.structured_workout import (
    RampStep,
    RepeatStep,
    SteadyStep,
    StepDuration,
    StepDurationUnit,
    TargetUnit,
    TimedDistanceStep,
    WorkoutStep,
    WorkoutTarget,
)


class WorkoutRenderError(ValueError):
    pass


def _clock(total_seconds: float) -> str:
    seconds = int(round(total_seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def _prompt(value: str | None, *, fallback: str | None = None) -> str | None:
    """Return one parser-safe prompt line without changing its words."""
    normalized = " ".join((value or fallback or "").split())
    return normalized or None


def _duration(value: StepDuration) -> str:
    if value.unit == StepDurationUnit.UNTIL_LAP_PRESS:
        assert value.nominal_seconds is not None
        return _duration(
            StepDuration(unit=StepDurationUnit.SECONDS, value=value.nominal_seconds)
        )
    if value.unit == StepDurationUnit.METERS:
        # Intervals uses "m" for minutes. "mtr" is the unambiguous metre token.
        return f"{value.value}mtr"
    seconds = int(value.value or 0)
    if seconds % 60 == 0:
        return f"{seconds // 60}m"
    return f"{seconds}s"


def _target(value: WorkoutTarget) -> str:
    minimum = value.minimum
    maximum = value.maximum
    if value.unit == TargetUnit.SECONDS_PER_KILOMETER:
        return f"{_clock(minimum)}-{_clock(maximum)}/km"
    if value.unit == TargetUnit.BEATS_PER_MINUTE:
        return f"{round(minimum)}-{round(maximum)} bpm"
    if value.unit == TargetUnit.PERCENT_LTHR:
        return f"{minimum:g}-{maximum:g}% LTHR"
    if value.unit == TargetUnit.PERCENT_MAX_HEART_RATE:
        return f"{minimum:g}-{maximum:g}% HR"
    if value.unit == TargetUnit.WATTS:
        return f"{round(minimum)}-{round(maximum)}w"
    if value.unit == TargetUnit.PERCENT_FTP:
        return f"{minimum:g}-{maximum:g}% FTP"
    raise WorkoutRenderError(f"Unsupported target unit: {value.unit}")


def _ramp_target(start: WorkoutTarget, end: WorkoutTarget) -> str:
    if start.mode != end.mode or start.unit != end.unit:
        raise WorkoutRenderError("Ramp endpoints must use one target mode and unit")
    if start.minimum != start.maximum or end.minimum != end.maximum:
        raise WorkoutRenderError("Ramp publication requires scalar endpoint targets")
    first = start.minimum
    second = end.minimum
    if start.unit == TargetUnit.SECONDS_PER_KILOMETER:
        return f"{_clock(first)}-{_clock(second)}/km"
    if start.unit == TargetUnit.BEATS_PER_MINUTE:
        return f"{round(first)}-{round(second)} bpm"
    if start.unit == TargetUnit.PERCENT_LTHR:
        return f"{first:g}-{second:g}% LTHR"
    if start.unit == TargetUnit.PERCENT_MAX_HEART_RATE:
        return f"{first:g}-{second:g}% HR"
    if start.unit == TargetUnit.WATTS:
        return f"{round(first)}-{round(second)}w"
    if start.unit == TargetUnit.PERCENT_FTP:
        return f"{first:g}-{second:g}% FTP"
    raise WorkoutRenderError(f"Unsupported ramp target unit: {start.unit}")


def _render_step(step: WorkoutStep, indent: str = "") -> list[str]:
    if isinstance(step, RepeatStep):
        repeat_prompt = _prompt(step.cue, fallback="Repeat")
        lines = [f"{indent}{repeat_prompt} {step.repetitions}x"]
        for child in step.steps:
            lines.extend(_render_step(child, indent + "  "))
        return lines

    if isinstance(step, SteadyStep):
        pieces = [f"{indent}-"]
        prompt = _prompt(
            step.cue,
            fallback=(
                "Press lap"
                if step.duration.unit == StepDurationUnit.UNTIL_LAP_PRESS
                else None
            ),
        )
        if prompt:
            pieces.append(prompt)
        pieces.append(_duration(step.duration))
        if step.target:
            pieces.append(_target(step.target))
        pieces.append(f"intensity={step.intensity}")
        if step.cadence:
            pieces.append(
                f"{step.cadence.minimum_revolutions_per_minute}-"
                f"{step.cadence.maximum_revolutions_per_minute} rpm"
            )
        return [" ".join(pieces)]

    if isinstance(step, RampStep):
        pieces = [f"{indent}-"]
        prompt = _prompt(
            step.cue,
            fallback=(
                "Press lap"
                if step.duration.unit == StepDurationUnit.UNTIL_LAP_PRESS
                else None
            ),
        )
        if prompt:
            pieces.append(prompt)
        pieces.extend(
            (
                _duration(step.duration),
                f"ramp {_ramp_target(step.start_target, step.end_target)}",
                f"intensity={step.intensity}",
            )
        )
        if step.cadence:
            pieces.append(
                f"{step.cadence.minimum_revolutions_per_minute}-"
                f"{step.cadence.maximum_revolutions_per_minute} rpm"
            )
        return [" ".join(pieces)]

    if isinstance(step, TimedDistanceStep):
        distance_meters = f"{step.distance_meters:g}mtr"
        prompt = _prompt(step.cue, fallback="Time trial")
        assert prompt is not None
        pieces = [
            f"{indent}-",
            prompt,
            distance_meters,
            "intensity=interval",
        ]
        return [" ".join(pieces)]

    raise WorkoutRenderError(f"Unsupported workout step: {type(step).__name__}")


def render_structured_workout(steps: list[WorkoutStep]) -> str:
    lines: list[str] = []
    for step in steps:
        lines.extend(_render_step(step))
    return "\n".join(lines) + "\n"

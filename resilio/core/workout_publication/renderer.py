"""Deterministic native workout-text rendering."""

from __future__ import annotations

from resilio.schemas.structured_workout import (
    RampStep,
    RepeatStep,
    SteadyStep,
    StepDuration,
    StepDurationUnit,
    TargetUnit,
    WorkoutStep,
    WorkoutTarget,
)


class WorkoutRenderError(ValueError):
    pass


def _clock(total_seconds: float) -> str:
    seconds = int(round(total_seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def _duration(value: StepDuration) -> str:
    if value.unit == StepDurationUnit.UNTIL_LAP_PRESS:
        return "lap"
    if value.unit == StepDurationUnit.METERS:
        return f"{value.value}m"
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
        return f"{minimum:g}-{maximum:g}% max HR"
    if value.unit == TargetUnit.WATTS:
        return f"{round(minimum)}-{round(maximum)}w"
    if value.unit == TargetUnit.PERCENT_FTP:
        return f"{minimum:g}-{maximum:g}% FTP"
    raise WorkoutRenderError(f"Unsupported target unit: {value.unit}")


def _render_step(step: WorkoutStep, indent: str = "") -> list[str]:
    if isinstance(step, RepeatStep):
        lines = [f"{indent}{step.repetitions}x"]
        if step.cue:
            lines[0] += f" {step.cue.strip()}"
        for child in step.steps:
            lines.extend(_render_step(child, indent + "  "))
        return lines

    if isinstance(step, SteadyStep):
        pieces = [f"{indent}-", _duration(step.duration)]
        if step.target:
            pieces.append(_target(step.target))
        pieces.append(str(step.intensity))
        if step.cadence:
            pieces.append(
                f"{step.cadence.minimum_revolutions_per_minute}-"
                f"{step.cadence.maximum_revolutions_per_minute} rpm"
            )
        if step.cue:
            pieces.append(step.cue.strip())
        return [" ".join(pieces)]

    if isinstance(step, RampStep):
        if step.start_target.mode != step.end_target.mode:
            raise WorkoutRenderError("Ramp endpoints must use one target mode")
        pieces = [
            f"{indent}-",
            _duration(step.duration),
            f"ramp {_target(step.start_target)} to {_target(step.end_target)}",
            str(step.intensity),
        ]
        if step.cadence:
            pieces.append(
                f"{step.cadence.minimum_revolutions_per_minute}-"
                f"{step.cadence.maximum_revolutions_per_minute} rpm"
            )
        if step.cue:
            pieces.append(step.cue.strip())
        return [" ".join(pieces)]

    raise WorkoutRenderError(f"Unsupported workout step: {type(step).__name__}")


def render_structured_workout(steps: list[WorkoutStep]) -> str:
    lines: list[str] = []
    for step in steps:
        lines.extend(_render_step(step))
    return "\n".join(lines) + "\n"

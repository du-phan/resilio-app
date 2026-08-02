"""Provider-neutral comparison of prescribed and parsed workout execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

from resilio.integrations.intervals_icu.dto import (
    WorkoutDocumentDTO,
    WorkoutDocumentStepDTO,
    WorkoutStepTargetDTO,
)
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


class WorkoutSemanticsError(ValueError):
    """A parsed provider workout does not preserve its prescription."""


TerminationKind = Literal["time", "distance", "lap"]


@dataclass(frozen=True)
class TargetSemantics:
    mode: Literal["pace", "heart_rate", "power"]
    unit: str
    minimum: float
    maximum: float
    ramp: bool = False


@dataclass(frozen=True)
class StepSemantics:
    termination_kind: TerminationKind
    termination_value: float | None
    intensity: str
    prompt: str | None
    target: TargetSemantics | None
    press_lap: bool = False
    cadence_minimum_revolutions_per_minute: float | None = None
    cadence_maximum_revolutions_per_minute: float | None = None


def _clean_prompt(value: str | None) -> str | None:
    cleaned = " ".join((value or "").split())
    return cleaned or None


def _expected_termination(duration: StepDuration) -> tuple[TerminationKind, float | None]:
    if duration.unit == StepDurationUnit.SECONDS:
        assert duration.value is not None
        return "time", float(duration.value)
    if duration.unit == StepDurationUnit.METERS:
        assert duration.value is not None
        return "distance", float(duration.value)
    assert duration.nominal_seconds is not None
    return "time", float(duration.nominal_seconds)


def _expected_target(target: WorkoutTarget, *, ramp: bool = False) -> TargetSemantics:
    unit = {
        TargetUnit.SECONDS_PER_KILOMETER: "secs/km",
        TargetUnit.BEATS_PER_MINUTE: "bpm",
        TargetUnit.PERCENT_LTHR: "%lthr",
        TargetUnit.PERCENT_MAX_HEART_RATE: "%hr",
        TargetUnit.WATTS: "w",
        TargetUnit.PERCENT_FTP: "%ftp",
    }[target.unit]
    return TargetSemantics(
        mode=cast(Literal["pace", "heart_rate", "power"], str(target.mode)),
        unit=unit,
        minimum=float(target.minimum),
        maximum=float(target.maximum),
        ramp=ramp,
    )


def expected_workout_semantics(steps: list[WorkoutStep]) -> tuple[StepSemantics, ...]:
    """Expand a local workout tree into its ordered execution semantics."""
    expanded: list[StepSemantics] = []

    def visit(step: WorkoutStep) -> None:
        if isinstance(step, RepeatStep):
            for _ in range(step.repetitions):
                for child in step.steps:
                    visit(child)
            return
        if isinstance(step, TimedDistanceStep):
            expanded.append(
                StepSemantics(
                    termination_kind="distance",
                    termination_value=float(step.distance_meters),
                    intensity="interval",
                    prompt=_clean_prompt(step.cue),
                    target=None,
                    press_lap=False,
                )
            )
            return
        termination_kind, termination_value = _expected_termination(step.duration)
        target: TargetSemantics | None
        if isinstance(step, RampStep):
            if (
                step.start_target.minimum != step.start_target.maximum
                or step.end_target.minimum != step.end_target.maximum
            ):
                raise WorkoutSemanticsError(
                    "Intervals ramp publication requires scalar endpoint targets"
                )
            target = _expected_target(
                step.start_target.model_copy(
                    update={"maximum": step.end_target.maximum}
                ),
                ramp=True,
            )
        else:
            assert isinstance(step, SteadyStep)
            target = _expected_target(step.target) if step.target else None
        cadence = step.cadence
        expanded.append(
            StepSemantics(
                termination_kind=termination_kind,
                termination_value=termination_value,
                intensity=str(step.intensity),
                prompt=_clean_prompt(step.cue),
                target=target,
                press_lap=step.duration.unit == StepDurationUnit.UNTIL_LAP_PRESS,
                cadence_minimum_revolutions_per_minute=(
                    float(cadence.minimum_revolutions_per_minute) if cadence else None
                ),
                cadence_maximum_revolutions_per_minute=(
                    float(cadence.maximum_revolutions_per_minute) if cadence else None
                ),
            )
        )

    for root in steps:
        visit(root)
    return tuple(expanded)


def _provider_target(
    step: WorkoutDocumentStepDTO,
) -> TargetSemantics | None:
    candidates = [
        ("pace", step.pace),
        ("heart_rate", step.heart_rate),
        ("power", step.power),
    ]
    populated = [(mode, value) for mode, value in candidates if value is not None]
    if len(populated) > 1:
        raise WorkoutSemanticsError("provider step has multiple target modes")
    if not populated:
        return None
    mode, target = populated[0]
    assert target is not None
    minimum, maximum = _provider_target_bounds(
        target,
        preserve_order=step.ramp,
    )
    return TargetSemantics(
        mode=mode,  # type: ignore[arg-type]
        unit=_canonical_target_unit(target.units),
        minimum=minimum,
        maximum=maximum,
        ramp=step.ramp,
    )


def _provider_target_bounds(
    target: WorkoutStepTargetDTO,
    *,
    preserve_order: bool = False,
) -> tuple[float, float]:
    if target.value is not None:
        return float(target.value), float(target.value)
    assert target.start is not None and target.end is not None
    if not preserve_order and target.units.casefold() in {"secs/km", "secs/mi"}:
        return min(target.start, target.end), max(target.start, target.end)
    return float(target.start), float(target.end)


def _canonical_target_unit(value: str) -> str:
    compact = value.strip().casefold().replace(" ", "")
    aliases = {
        "sec/km": "secs/km",
        "seconds/km": "secs/km",
        "bpm": "bpm",
        "%lthr": "%lthr",
        "%hr": "%hr",
        "%hrmax": "%hr",
        "watts": "w",
        "w": "w",
        "%ftp": "%ftp",
    }
    return aliases.get(compact, compact)


def _provider_intensity(step: WorkoutDocumentStepDTO) -> str:
    if step.intensity:
        return step.intensity.casefold()
    if step.warmup:
        return "warmup"
    if step.cooldown:
        return "cooldown"
    raise WorkoutSemanticsError("provider step has no explicit intensity")


def provider_workout_semantics(document: WorkoutDocumentDTO) -> tuple[StepSemantics, ...]:
    """Expand a parsed Intervals document into ordered execution semantics."""
    expanded: list[StepSemantics] = []

    def visit(step: WorkoutDocumentStepDTO) -> None:
        if step.steps:
            if step.repetitions is None:
                raise WorkoutSemanticsError("provider repeat block has no repetition count")
            for _ in range(step.repetitions):
                for child in step.steps:
                    visit(child)
            return
        if step.distance_meters is not None:
            termination_kind: TerminationKind = "distance"
            termination_value = step.distance_meters
        elif step.duration_seconds is not None:
            termination_kind = "time"
            termination_value = step.duration_seconds
        elif step.press_lap:
            termination_kind = "lap"
            termination_value = None
        else:
            raise WorkoutSemanticsError("provider step has no termination")
        cadence_minimum = cadence_maximum = None
        if step.cadence is not None:
            cadence_minimum, cadence_maximum = _provider_target_bounds(step.cadence)
        expanded.append(
            StepSemantics(
                termination_kind=termination_kind,
                termination_value=termination_value,
                intensity=_provider_intensity(step),
                prompt=_clean_prompt(step.text),
                target=_provider_target(step),
                press_lap=step.press_lap,
                cadence_minimum_revolutions_per_minute=cadence_minimum,
                cadence_maximum_revolutions_per_minute=cadence_maximum,
            )
        )

    for root in document.steps:
        visit(root)
    if not expanded:
        raise WorkoutSemanticsError("provider workout document has no executable steps")
    return tuple(expanded)


def assert_workout_semantics_match(
    expected: tuple[StepSemantics, ...],
    document: WorkoutDocumentDTO,
) -> None:
    """Require provider readback to preserve every prescribed execution step."""
    actual = provider_workout_semantics(document)
    if len(actual) != len(expected):
        raise WorkoutSemanticsError(
            f"provider has {len(actual)} executable steps; expected {len(expected)}"
        )
    for index, (expected_step, actual_step) in enumerate(zip(expected, actual), start=1):
        if (
            expected_step.termination_kind != actual_step.termination_kind
            or not _optional_number_equal(
                expected_step.termination_value,
                actual_step.termination_value,
            )
            or expected_step.intensity != actual_step.intensity
            or expected_step.target != actual_step.target
            or expected_step.press_lap != actual_step.press_lap
            or not _optional_number_equal(
                expected_step.cadence_minimum_revolutions_per_minute,
                actual_step.cadence_minimum_revolutions_per_minute,
            )
            or not _optional_number_equal(
                expected_step.cadence_maximum_revolutions_per_minute,
                actual_step.cadence_maximum_revolutions_per_minute,
            )
            or not _prompt_preserved(expected_step.prompt, actual_step.prompt)
        ):
            raise WorkoutSemanticsError(
                f"provider semantics mismatch at executable step {index}"
            )


def _optional_number_equal(left: float | None, right: float | None) -> bool:
    if left is None or right is None:
        return left is right
    return abs(left - right) <= 1e-6


def _prompt_preserved(expected: str | None, actual: str | None) -> bool:
    if expected is None:
        return True
    if actual is None:
        return False
    return expected.casefold() in actual.casefold()

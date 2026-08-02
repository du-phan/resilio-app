"""Provider-neutral structured workout tree."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WorkoutSport(str, Enum):
    RUN = "run"
    CYCLE = "cycle"


class StepDurationUnit(str, Enum):
    SECONDS = "seconds"
    METERS = "meters"
    UNTIL_LAP_PRESS = "until_lap_press"


class StepDuration(BaseModel):
    unit: StepDurationUnit
    value: Optional[int] = Field(default=None, gt=0)
    nominal_seconds: Optional[int] = Field(default=None, gt=0)

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    @model_validator(mode="after")
    def validate_duration_variant(self) -> "StepDuration":
        if self.unit == StepDurationUnit.UNTIL_LAP_PRESS:
            if self.value is not None:
                raise ValueError("until_lap_press duration cannot have a fixed value")
            if self.nominal_seconds is None:
                raise ValueError(
                    "until_lap_press duration requires nominal_seconds for load calculation"
                )
        elif self.value is None:
            raise ValueError("fixed duration requires value")
        elif self.unit == StepDurationUnit.METERS:
            if self.nominal_seconds is None:
                raise ValueError(
                    "distance duration requires nominal_seconds for exact " "session planning"
                )
        elif self.nominal_seconds is not None:
            raise ValueError(
                "nominal_seconds is only valid with distance or " "until_lap_press duration"
            )
        return self


class TargetMode(str, Enum):
    PACE = "pace"
    HEART_RATE = "heart_rate"
    POWER = "power"


class TargetUnit(str, Enum):
    SECONDS_PER_KILOMETER = "seconds_per_kilometer"
    BEATS_PER_MINUTE = "beats_per_minute"
    PERCENT_LTHR = "percent_lthr"
    PERCENT_MAX_HEART_RATE = "percent_max_heart_rate"
    WATTS = "watts"
    PERCENT_FTP = "percent_ftp"


class WorkoutTarget(BaseModel):
    mode: TargetMode
    unit: TargetUnit
    minimum: float = Field(gt=0, allow_inf_nan=False)
    maximum: float = Field(gt=0, allow_inf_nan=False)

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    @model_validator(mode="after")
    def validate_target(self) -> "WorkoutTarget":
        allowed = {
            TargetMode.PACE: {TargetUnit.SECONDS_PER_KILOMETER},
            TargetMode.HEART_RATE: {
                TargetUnit.BEATS_PER_MINUTE,
                TargetUnit.PERCENT_LTHR,
                TargetUnit.PERCENT_MAX_HEART_RATE,
            },
            TargetMode.POWER: {TargetUnit.WATTS, TargetUnit.PERCENT_FTP},
        }
        if self.unit not in allowed[self.mode]:
            raise ValueError(f"{self.unit} is not valid for {self.mode}")
        if self.minimum > self.maximum:
            raise ValueError("target minimum cannot exceed maximum")
        if (
            self.unit
            in {
                TargetUnit.PERCENT_LTHR,
                TargetUnit.PERCENT_MAX_HEART_RATE,
                TargetUnit.PERCENT_FTP,
            }
            and self.maximum > 200
        ):
            raise ValueError("percentage targets cannot exceed 200")
        return self


class StepIntensity(str, Enum):
    WARMUP = "warmup"
    INTERVAL = "interval"
    RECOVERY = "recovery"
    COOLDOWN = "cooldown"
    ACTIVE = "active"
    REST = "rest"
    OTHER = "other"


class CadenceRange(BaseModel):
    minimum_revolutions_per_minute: int = Field(gt=0, le=300)
    maximum_revolutions_per_minute: int = Field(gt=0, le=300)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def ordered(self) -> "CadenceRange":
        if self.minimum_revolutions_per_minute > self.maximum_revolutions_per_minute:
            raise ValueError("cadence minimum cannot exceed maximum")
        return self


class SteadyStep(BaseModel):
    kind: Literal["steady"] = "steady"
    duration: StepDuration
    target: Optional[WorkoutTarget] = None
    intensity: StepIntensity
    cadence: Optional[CadenceRange] = None
    cue: Optional[str] = Field(default=None, max_length=500)

    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class RampStep(BaseModel):
    kind: Literal["ramp"] = "ramp"
    duration: StepDuration
    start_target: WorkoutTarget
    end_target: WorkoutTarget
    intensity: StepIntensity
    cadence: Optional[CadenceRange] = None
    cue: Optional[str] = Field(default=None, max_length=500)

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    @model_validator(mode="after")
    def consistent_target_mode(self) -> "RampStep":
        if (
            self.start_target.mode != self.end_target.mode
            or self.start_target.unit != self.end_target.unit
        ):
            raise ValueError("ramp endpoints must use the same target mode and unit")
        return self


class TimedDistanceStep(BaseModel):
    """One untargeted measured effort over an athlete-confirmed distance."""

    kind: Literal["timed_distance"] = "timed_distance"
    distance_meters: float = Field(gt=0, allow_inf_nan=False)
    nominal_seconds: int = Field(gt=0)
    cue: Optional[str] = Field(default=None, max_length=500)

    model_config = ConfigDict(extra="forbid")


class RepeatStep(BaseModel):
    kind: Literal["repeat"] = "repeat"
    repetitions: int = Field(ge=2, le=100)
    steps: list["WorkoutStep"] = Field(min_length=1)
    cue: Optional[str] = Field(default=None, max_length=500)

    model_config = ConfigDict(extra="forbid")


WorkoutStep = Annotated[
    Union[SteadyStep, RampStep, TimedDistanceStep, RepeatStep],
    Field(discriminator="kind"),
]


class StructuredWorkout(BaseModel):
    sport: WorkoutSport
    steps: list[WorkoutStep] = Field(min_length=1)

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    def target_modes(self) -> set[str]:
        modes: set[str] = set()

        def visit(step: WorkoutStep) -> None:
            if isinstance(step, SteadyStep) and step.target:
                modes.add(str(step.target.mode))
            elif isinstance(step, RampStep):
                modes.add(str(step.start_target.mode))
            elif isinstance(step, RepeatStep):
                for child in step.steps:
                    visit(child)

        for root in self.steps:
            visit(root)
        return modes

    def targets(self) -> list[WorkoutTarget]:
        """Return all explicit targets in deterministic depth-first order."""

        targets: list[WorkoutTarget] = []

        def visit(step: WorkoutStep) -> None:
            if isinstance(step, SteadyStep) and step.target is not None:
                targets.append(step.target)
            elif isinstance(step, RampStep):
                targets.extend((step.start_target, step.end_target))
            elif isinstance(step, RepeatStep):
                for child in step.steps:
                    visit(child)

        for root in self.steps:
            visit(root)
        return targets

    def uses_lap_press(self) -> bool:
        def visit(step: WorkoutStep) -> bool:
            if isinstance(step, (SteadyStep, RampStep)):
                return step.duration.unit == StepDurationUnit.UNTIL_LAP_PRESS
            if isinstance(step, TimedDistanceStep):
                return False
            return any(visit(child) for child in step.steps)

        return any(visit(step) for step in self.steps)

    def nominal_duration_seconds(self) -> int:
        """Return the exact recursively expanded planning duration."""

        def duration(step: WorkoutStep) -> int:
            if isinstance(step, RepeatStep):
                return step.repetitions * sum(duration(child) for child in step.steps)
            if isinstance(step, TimedDistanceStep):
                return step.nominal_seconds
            if step.duration.unit == StepDurationUnit.SECONDS:
                assert step.duration.value is not None
                return step.duration.value
            assert step.duration.nominal_seconds is not None
            return step.duration.nominal_seconds

        return sum(duration(step) for step in self.steps)

    def timed_distance_steps(self) -> list[TimedDistanceStep]:
        """Return timed-distance steps in deterministic depth-first order."""

        timed_steps: list[TimedDistanceStep] = []

        def visit(step: WorkoutStep) -> None:
            if isinstance(step, TimedDistanceStep):
                timed_steps.append(step)
            elif isinstance(step, RepeatStep):
                for child in step.steps:
                    visit(child)

        for root in self.steps:
            visit(root)
        return timed_steps


RepeatStep.model_rebuild()
StructuredWorkout.model_rebuild()

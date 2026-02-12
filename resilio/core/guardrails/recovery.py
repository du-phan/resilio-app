"""
Recovery calculation protocols.

Implements return-to-training protocols from Daniels' Running Formula (Table 9.2)
and Pfitzinger's masters/race recovery guidelines.
"""

from typing import Optional
from datetime import date, timedelta
from resilio.schemas.guardrails import (
    BreakReturnPlan,
    MastersRecoveryAdjustment,
    RaceRecoveryPlan,
    IllnessRecoveryPlan,
    WeekSchedule,
    DayActivity,
    IllnessSeverity,
)


# ============================================================
# BREAK RETURN PLANNING (DANIELS TABLE 9.2)
# ============================================================


def calculate_break_return_plan(
    break_days: int,
    pre_break_ctl: float,
    cross_training_level: str = "none",
) -> BreakReturnPlan:
    """
    Generate return-to-training protocol per Daniels Table 9.2.

    Daniels' guidelines:
    - ≤5 days: 100% load, 100% VDOT
    - 6-28 days: 50% first half, 75% second half, 93-99% VDOT
    - >8 weeks: Structured multi-week (33%, 50%, 75%), 80-92% VDOT

    Args:
        break_days: Duration of training break
        pre_break_ctl: CTL before the break
        cross_training_level: Level of cross-training ("none", "light", "moderate", "heavy")

    Returns:
        BreakReturnPlan with week-by-week schedule

    Example:
        >>> plan = calculate_break_return_plan(21, 44.0, "moderate")
        >>> print(f"Return in {plan.estimated_full_return_weeks} weeks")
    """
    # Determine adjustments based on break duration (Daniels Table 9.2)
    if break_days <= 5:
        # Minimal break - resume immediately
        load_phase_1_pct = 100
        load_phase_2_pct = 100
        vdot_adjustment_pct = 100
        return_weeks = 1
        schedule = [
            WeekSchedule(
                week_number=1,
                load_pct=100,
                volume_km=None,
                description="Resume normal training immediately",
            )
        ]

    elif break_days <= 28:  # 6-28 days (Daniels: "few weeks")
        # Short break - gradual return
        load_phase_1_pct = 50  # First half of return period
        load_phase_2_pct = 75  # Second half
        vdot_adjustment_pct = 95  # Slight VDOT reduction

        # Cross-training modifier
        if cross_training_level == "heavy":
            vdot_adjustment_pct = 99  # Maintained more fitness
        elif cross_training_level == "moderate":
            vdot_adjustment_pct = 97
        elif cross_training_level == "light":
            vdot_adjustment_pct = 95
        else:  # none
            vdot_adjustment_pct = 93

        # Return period = break duration (if 3 weeks off, 3 weeks to return)
        return_weeks = max(2, break_days // 7)

        schedule = []
        for week in range(1, return_weeks + 1):
            if week <= return_weeks // 2:
                # First half at 50%
                schedule.append(
                    WeekSchedule(
                        week_number=week,
                        load_pct=load_phase_1_pct,
                        volume_km=None,
                        description="Easy runs only, monitor for soreness",
                    )
                )
            else:
                # Second half at 75%
                schedule.append(
                    WeekSchedule(
                        week_number=week,
                        load_pct=load_phase_2_pct,
                        volume_km=None,
                        description="Add one quality session if feeling good",
                    )
                )

        # Final week to 100%
        schedule.append(
            WeekSchedule(
                week_number=return_weeks + 1,
                load_pct=100,
                volume_km=None,
                description="Resume full training",
            )
        )
        return_weeks += 1

    else:  # >28 days (long break)
        # Extended break - conservative return (Daniels: >8 weeks)
        load_phase_1_pct = 33
        load_phase_2_pct = 50
        vdot_adjustment_pct = 85  # Significant fitness loss

        # Cross-training modifier
        if cross_training_level == "heavy":
            vdot_adjustment_pct = 92
        elif cross_training_level == "moderate":
            vdot_adjustment_pct = 88
        elif cross_training_level == "light":
            vdot_adjustment_pct = 85
        else:  # none
            vdot_adjustment_pct = 80

        return_weeks = max(4, break_days // 10)  # Conservative: 10:1 ratio

        # Phase 1: 33% load (first 1/3 of return)
        phase_1_weeks = return_weeks // 3
        # Phase 2: 50% load (second 1/3)
        phase_2_weeks = return_weeks // 3
        # Phase 3: 75% load (final 1/3)
        phase_3_weeks = return_weeks - phase_1_weeks - phase_2_weeks

        schedule = []
        week_num = 1

        for _ in range(phase_1_weeks):
            schedule.append(
                WeekSchedule(
                    week_number=week_num,
                    load_pct=33,
                    volume_km=None,
                    description="Very easy runs, rebuild aerobic base",
                )
            )
            week_num += 1

        for _ in range(phase_2_weeks):
            schedule.append(
                WeekSchedule(
                    week_number=week_num,
                    load_pct=50,
                    volume_km=None,
                    description="Easy runs, build volume gradually",
                )
            )
            week_num += 1

        for _ in range(phase_3_weeks):
            schedule.append(
                WeekSchedule(
                    week_number=week_num,
                    load_pct=75,
                    volume_km=None,
                    description="Add quality work if feeling strong",
                )
            )
            week_num += 1

        schedule.append(
            WeekSchedule(
                week_number=week_num,
                load_pct=100,
                volume_km=None,
                description="Resume full training",
            )
        )
        return_weeks = week_num

    # Red flags
    red_flags = [
        "Monitor for excessive soreness or fatigue",
        "If struggling, extend current phase by 1 week",
        "Don't rush - fitness returns faster than initial build",
    ]

    if break_days > 14:
        red_flags.append("Consider testing VDOT with 5K time trial before resuming threshold work")

    return BreakReturnPlan(
        break_duration_days=break_days,
        pre_break_ctl=pre_break_ctl,
        cross_training_level=cross_training_level,
        load_phase_1_pct=load_phase_1_pct,
        load_phase_2_pct=load_phase_2_pct,
        vdot_adjustment_pct=vdot_adjustment_pct,
        return_schedule=schedule,
        estimated_full_return_weeks=return_weeks,
        red_flags=red_flags,
    )


# ============================================================
# MASTERS RECOVERY (PFITZINGER)
# ============================================================


def calculate_masters_recovery(
    age: int,
    workout_type: str,
) -> MastersRecoveryAdjustment:
    """
    Calculate age-specific recovery adjustments for masters athletes.

    Pfitzinger guidelines:
    - Age 18-45: Standard recovery (1 day after quality)
    - Age 46-55: +1-2 days after quality
    - Age 56-65: +2-3 days after quality
    - Age 65+: +3-4 days after quality

    Args:
        age: Athlete age
        workout_type: Type of workout ("vo2max", "tempo", "long_run", "easy", "race")

    Returns:
        MastersRecoveryAdjustment with recommended recovery days

    Example:
        >>> adjustment = calculate_masters_recovery(52, "vo2max")
        >>> print(f"Recovery needed: {adjustment.recommended_recovery_days['vo2max']} days")
    """
    # Determine age bracket
    if age < 46:
        age_bracket = "18-45"
        base_recovery = 1
        adjustments = {"vo2max": 0, "tempo": 0, "long_run": 0, "race": 0}
    elif age < 56:
        age_bracket = "46-55"
        base_recovery = 1
        adjustments = {"vo2max": 2, "tempo": 1, "long_run": 1, "race": 2}
    elif age < 66:
        age_bracket = "56-65"
        base_recovery = 1
        adjustments = {"vo2max": 3, "tempo": 2, "long_run": 2, "race": 3}
    else:  # 65+
        age_bracket = "65+"
        base_recovery = 2
        adjustments = {"vo2max": 4, "tempo": 3, "long_run": 3, "race": 4}

    # Calculate total recommended recovery for each workout type
    recommended_recovery = {
        workout_type: base_recovery + adj for workout_type, adj in adjustments.items()
    }

    # Add easy run recovery (always 0 additional)
    adjustments["easy"] = 0
    recommended_recovery["easy"] = 1  # Can run easy every day

    note = "Consider additional rest if fatigue elevated or readiness low"
    if age >= 56:
        note += ". Prioritize recovery over hitting exact schedule."

    return MastersRecoveryAdjustment(
        age=age,
        age_bracket=age_bracket,
        base_recovery_days=base_recovery,
        adjustments=adjustments,
        recommended_recovery_days=recommended_recovery,
        note=note,
    )


# ============================================================
# RACE RECOVERY (PFITZINGER)
# ============================================================


def calculate_race_recovery(
    race_distance: str,
    athlete_age: int,
    finishing_effort: str = "hard",
) -> RaceRecoveryPlan:
    """
    Determine post-race recovery protocol.

    Pfitzinger masters table (base recovery by distance):
    - 5K: 3-5 days
    - 10K: 5-7 days
    - Half: 7-10 days (age 18-45), 9-13 days (age 50-59)
    - Marathon: 14-21 days (age 18-45), 18-26 days (age 50-59)

    Args:
        race_distance: Race distance ("5k", "10k", "half_marathon", "marathon")
        athlete_age: Athlete age
        finishing_effort: Effort level ("easy", "moderate", "hard", "max")

    Returns:
        RaceRecoveryPlan with schedule and recommendations

    Example:
        >>> plan = calculate_race_recovery("half_marathon", 52, "hard")
        >>> print(f"Resume quality work on day {plan.quality_work_resume_day}")
    """
    # Base recovery by distance and age
    if race_distance == "5k":
        if athlete_age < 46:
            min_days, rec_days = 3, 5
        elif athlete_age < 56:
            min_days, rec_days = 4, 6
        else:
            min_days, rec_days = 5, 7

    elif race_distance == "10k":
        if athlete_age < 46:
            min_days, rec_days = 5, 7
        elif athlete_age < 56:
            min_days, rec_days = 6, 8
        else:
            min_days, rec_days = 7, 9

    elif race_distance == "half_marathon":
        if athlete_age < 46:
            min_days, rec_days = 7, 10
        elif athlete_age < 56:
            min_days, rec_days = 9, 13
        else:
            min_days, rec_days = 11, 15

    elif race_distance == "marathon":
        if athlete_age < 46:
            min_days, rec_days = 14, 21
        elif athlete_age < 56:
            min_days, rec_days = 18, 26
        else:
            min_days, rec_days = 21, 30

    else:
        # Default for unknown distance
        min_days, rec_days = 7, 10

    # Adjust for effort level
    effort_multipliers = {
        "easy": 0.7,
        "moderate": 0.85,
        "hard": 1.0,
        "max": 1.15,
    }
    multiplier = effort_multipliers.get(finishing_effort, 1.0)
    rec_days = int(rec_days * multiplier)

    # Build recovery schedule
    recovery_schedule = []

    # Immediate recovery phase (first 2 days)
    recovery_schedule.append("Day 1-2: Complete rest or light cross-training (walking, yoga)")

    # Early easy running phase
    early_phase_end = min(min_days, rec_days // 3)
    recovery_schedule.append(
        f"Day 3-{early_phase_end}: Easy 20-30min runs, RPE 3-4 max, stop if sharp pain"
    )

    # Gradual build phase
    mid_phase_end = (rec_days * 2) // 3
    recovery_schedule.append(
        f"Day {early_phase_end + 1}-{mid_phase_end}: Easy 30-45min runs, "
        f"can add one tempo if feeling fresh"
    )

    # Return to quality phase
    recovery_schedule.append(
        f"Day {mid_phase_end + 1}+: Resume normal training if readiness >70"
    )

    # Quality work resume day
    quality_work_resume_day = rec_days

    # Red flags
    red_flags = [
        "Persistent soreness beyond typical 2-3 days post-race",
        "Elevated resting heart rate (>5 bpm above baseline)",
        "Readiness score <50 after first week",
        "Sharp pain (stop immediately and rest additional days)",
    ]

    if race_distance in ["half_marathon", "marathon"]:
        red_flags.append(
            "For marathon: Expect 1 day of recovery per mile raced "
            "(26 days is normal, don't rush)"
        )

    return RaceRecoveryPlan(
        race_distance=race_distance,
        athlete_age=athlete_age,
        effort=finishing_effort,
        minimum_recovery_days=min_days,
        recommended_recovery_days=rec_days,
        recovery_schedule=recovery_schedule,
        quality_work_resume_day=quality_work_resume_day,
        red_flags=red_flags,
    )


# ============================================================
# ILLNESS RECOVERY
# ============================================================


def generate_illness_recovery_plan(
    illness_duration_days: int,
    severity: IllnessSeverity = IllnessSeverity.MODERATE,
) -> IllnessRecoveryPlan:
    """
    Generate structured return after illness.

    Guidelines:
    - Mild (1-3 days): Resume easy running after 1-2 rest days
    - Moderate (4-7 days): Resume after symptoms clear + 2 days
    - Severe (8+ days): Conservative return, 50% → 75% → 100% over 2 weeks

    Args:
        illness_duration_days: Days of illness
        severity: Illness severity level

    Returns:
        IllnessRecoveryPlan with day-by-day protocol

    Example:
        >>> plan = generate_illness_recovery_plan(5, IllnessSeverity.MODERATE)
        >>> print(f"Full training on day {plan.full_training_resume_day}")
    """
    # Estimate CTL drop (roughly 2 points per day off)
    estimated_ctl_drop = illness_duration_days * 2.0

    # Build return protocol based on severity
    return_protocol = []

    if severity == IllnessSeverity.MILD:
        # 1-3 days illness - quick return
        return_protocol = [
            DayActivity(day_number=1, activity="Rest", load_au=0, rpe_max=None),
            DayActivity(day_number=2, activity="20min easy walk", load_au=20, rpe_max=3),
            DayActivity(day_number=3, activity="Easy 20min run", load_au=60, rpe_max=4),
            DayActivity(day_number=5, activity="Easy 30min run", load_au=90, rpe_max=4),
            DayActivity(day_number=7, activity="Resume plan at 75% intensity", load_au=None, rpe_max=6),
        ]
        full_training_day = 10

    elif severity == IllnessSeverity.MODERATE:
        # 4-7 days illness - gradual return
        return_protocol = [
            DayActivity(day_number=1, activity="Rest", load_au=0, rpe_max=None),
            DayActivity(day_number=2, activity="Rest", load_au=0, rpe_max=None),
            DayActivity(day_number=3, activity="20min walk", load_au=20, rpe_max=3),
            DayActivity(day_number=4, activity="Rest", load_au=0, rpe_max=None),
            DayActivity(day_number=5, activity="Easy 20min run", load_au=60, rpe_max=4),
            DayActivity(day_number=7, activity="Easy 30min run", load_au=90, rpe_max=4),
            DayActivity(day_number=9, activity="Easy 40min run", load_au=120, rpe_max=5),
            DayActivity(day_number=11, activity="Resume plan at 50% intensity", load_au=None, rpe_max=5),
            DayActivity(day_number=14, activity="Resume plan at 75% intensity", load_au=None, rpe_max=6),
        ]
        full_training_day = 18

    else:  # SEVERE
        # 8+ days illness - very conservative
        return_protocol = [
            DayActivity(day_number=1, activity="Rest", load_au=0, rpe_max=None),
            DayActivity(day_number=2, activity="Rest", load_au=0, rpe_max=None),
            DayActivity(day_number=3, activity="Rest", load_au=0, rpe_max=None),
            DayActivity(day_number=4, activity="Light walk", load_au=15, rpe_max=2),
            DayActivity(day_number=6, activity="20min walk", load_au=20, rpe_max=3),
            DayActivity(day_number=8, activity="Easy 15min run", load_au=45, rpe_max=3),
            DayActivity(day_number=10, activity="Easy 20min run", load_au=60, rpe_max=4),
            DayActivity(day_number=12, activity="Easy 30min run", load_au=90, rpe_max=4),
            DayActivity(day_number=14, activity="Easy 40min run", load_au=120, rpe_max=5),
            DayActivity(day_number=17, activity="Resume plan at 50% intensity", load_au=None, rpe_max=5),
            DayActivity(day_number=21, activity="Resume plan at 75% intensity", load_au=None, rpe_max=6),
        ]
        full_training_day = 28

    # Red flags - signs to stop training
    red_flags = [
        "Elevated resting heart rate (>5 bpm above baseline)",
        "Persistent fatigue despite adequate rest",
        "Chest tightness or difficulty breathing",
        "Fever returns after initial recovery",
        "Dizziness or lightheadedness during exercise",
    ]

    # When to seek medical advice
    medical_triggers = [
        "Symptoms persist >7 days without improvement",
        "Fever >38.5°C (101.3°F)",
        "Chest pain or severe shortness of breath",
        "Symptoms worsen after starting return protocol",
    ]

    return IllnessRecoveryPlan(
        illness_duration_days=illness_duration_days,
        severity=severity,
        estimated_ctl_drop=estimated_ctl_drop,
        return_protocol=return_protocol,
        full_training_resume_day=full_training_day,
        red_flags=red_flags,
        medical_consultation_triggers=medical_triggers,
    )

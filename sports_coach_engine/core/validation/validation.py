"""Core validation functions (Phase 4).

This module implements:
1. validate_interval_structure() - Check interval work/recovery ratios per Daniels
2. validate_plan_structure() - Validate training plan skeleton (phases, volume, taper)
3. assess_goal_feasibility() - Assess goal realism based on VDOT and CTL
"""

from datetime import date, timedelta
from typing import List, Dict, Any, Optional
from sports_coach_engine.schemas.validation import (
    IntervalStructureValidation,
    IntervalBout,
    RecoveryBout,
    Violation,
    PlanStructureValidation,
    PhaseCheck,
    VolumeProgressionCheck,
    PeakPlacementCheck,
    RecoveryWeekCheck,
    TaperStructureCheck,
    GoalFeasibilityAssessment,
    CurrentFitness,
    GoalFitnessNeeded,
    TimeAvailable,
    FeasibilityAnalysis,
    AlternativeScenario,
)


# ============================================================================
# 1. Interval Structure Validation
# ============================================================================


def validate_interval_structure(
    workout_type: str,
    intensity: str,
    work_bouts: List[Dict[str, Any]],
    recovery_bouts: List[Dict[str, Any]],
    weekly_volume_km: Optional[float] = None,
) -> IntervalStructureValidation:
    """Validate interval workout structure per Daniels methodology.

    Daniels' rules:
    - I-pace (VO2max): 3-5min work bouts, equal recovery (jogging)
    - T-pace (threshold): 5-15min work bouts, 1min recovery per 5min work
    - R-pace (repetition): 30-90sec work bouts, 2-3x recovery time
    - Total I-pace volume ≤ lesser of 10km OR 8% weekly mileage
    - Total T-pace volume ≤ 10% weekly mileage
    - Total R-pace volume ≤ lesser of 8km OR 5% weekly mileage

    Args:
        workout_type: Workout type (e.g., "intervals", "tempo", "repetitions")
        intensity: Primary intensity (e.g., "I-pace", "T-pace", "R-pace")
        work_bouts: List of work bout dicts with 'duration_minutes', 'pace_per_km_seconds', 'distance_km'
        recovery_bouts: List of recovery bout dicts with 'duration_minutes', 'type'
        weekly_volume_km: Optional weekly volume for total volume validation

    Returns:
        IntervalStructureValidation with compliance analysis
    """
    # Daniels constraints
    IPACE_MIN_DURATION = 3.0  # minutes
    IPACE_MAX_DURATION = 5.0
    TPACE_MIN_DURATION = 5.0
    TPACE_MAX_DURATION = 15.0
    RPACE_MIN_DURATION = 0.5  # 30 seconds
    RPACE_MAX_DURATION = 1.5  # 90 seconds

    violations: List[Violation] = []
    recommendations: List[str] = []

    # Analyze work bouts
    work_bout_analysis: List[IntervalBout] = []
    total_work_minutes = 0.0
    total_work_km = 0.0

    for idx, bout in enumerate(work_bouts, 1):
        duration = bout.get("duration_minutes", 0)
        pace_per_km = bout.get("pace_per_km_seconds")
        distance_km = bout.get("distance_km", 0)
        total_work_minutes += duration
        total_work_km += distance_km

        # Check duration appropriateness
        ok = True
        issue = None

        if intensity == "I-pace":
            if duration < IPACE_MIN_DURATION:
                ok = False
                issue = f"Too short ({duration:.1f}min < {IPACE_MIN_DURATION}min minimum)"
                violations.append(
                    Violation(
                        type="I_PACE_WORK_BOUT_TOO_SHORT",
                        severity="MODERATE",
                        message=f"Work bout {idx} ({duration:.1f}min) below I-pace minimum ({IPACE_MIN_DURATION}min)",
                        recommendation=f"Increase to {IPACE_MIN_DURATION}-{IPACE_MAX_DURATION}min for VO2max stimulus",
                    )
                )
            elif duration > IPACE_MAX_DURATION:
                ok = False
                issue = f"Too long ({duration:.1f}min > {IPACE_MAX_DURATION}min maximum)"
                violations.append(
                    Violation(
                        type="I_PACE_WORK_BOUT_TOO_LONG",
                        severity="MODERATE",
                        message=f"Work bout {idx} ({duration:.1f}min) exceeds I-pace maximum ({IPACE_MAX_DURATION}min)",
                        recommendation=f"Split into 2x{duration/2:.1f}min bouts or reduce to {IPACE_MAX_DURATION}min",
                    )
                )
        elif intensity == "T-pace":
            if duration < TPACE_MIN_DURATION:
                ok = False
                issue = f"Too short ({duration:.1f}min < {TPACE_MIN_DURATION}min minimum)"
                violations.append(
                    Violation(
                        type="T_PACE_WORK_BOUT_TOO_SHORT",
                        severity="LOW",
                        message=f"Work bout {idx} ({duration:.1f}min) below T-pace typical minimum ({TPACE_MIN_DURATION}min)",
                        recommendation="Consider extending to 5-15min for threshold stimulus",
                    )
                )
            elif duration > TPACE_MAX_DURATION:
                ok = False
                issue = f"Too long ({duration:.1f}min > {TPACE_MAX_DURATION}min typical max)"
                violations.append(
                    Violation(
                        type="T_PACE_WORK_BOUT_TOO_LONG",
                        severity="LOW",
                        message=f"Work bout {idx} ({duration:.1f}min) exceeds T-pace typical maximum ({TPACE_MAX_DURATION}min)",
                        recommendation="Consider breaking into multiple bouts or running continuous tempo",
                    )
                )
        elif intensity == "R-pace":
            if duration < RPACE_MIN_DURATION:
                ok = False
                issue = f"Too short ({duration:.1f}min < {RPACE_MIN_DURATION}min minimum)"
                violations.append(
                    Violation(
                        type="R_PACE_WORK_BOUT_TOO_SHORT",
                        severity="LOW",
                        message=f"Work bout {idx} ({duration:.1f}min) below R-pace minimum (30sec)",
                        recommendation="R-pace intervals should be 30-90sec for speed development",
                    )
                )
            elif duration > RPACE_MAX_DURATION:
                ok = False
                issue = f"Too long ({duration:.1f}min > {RPACE_MAX_DURATION}min maximum)"
                violations.append(
                    Violation(
                        type="R_PACE_WORK_BOUT_TOO_LONG",
                        severity="MODERATE",
                        message=f"Work bout {idx} ({duration:.1f}min) exceeds R-pace maximum (90sec)",
                        recommendation="Reduce to 30-90sec for pure speed work",
                    )
                )

        work_bout_analysis.append(
            IntervalBout(
                duration_minutes=duration,
                pace_per_km_seconds=pace_per_km,
                intensity_zone=intensity,
                ok=ok,
                issue=issue,
            )
        )

    # Analyze recovery bouts
    recovery_bout_analysis: List[RecoveryBout] = []
    for idx, (work, recovery) in enumerate(zip(work_bouts, recovery_bouts), 1):
        work_duration = work.get("duration_minutes", 0)
        recovery_duration = recovery.get("duration_minutes", 0)
        recovery_type = recovery.get("type", "jog")

        ok = True
        issue = None

        if intensity == "I-pace":
            # I-pace: equal recovery (jogging)
            if recovery_duration < work_duration * 0.9:  # Allow 10% tolerance
                ok = False
                issue = f"Recovery too short ({recovery_duration:.1f}min < {work_duration:.1f}min work)"
                violations.append(
                    Violation(
                        type="I_PACE_RECOVERY_TOO_SHORT",
                        severity="MODERATE",
                        message=f"Recovery {idx} ({recovery_duration:.1f}min) less than work bout ({work_duration:.1f}min)",
                        recommendation=f"Increase recovery to {work_duration:.1f}min (equal to work) for I-pace",
                    )
                )
        elif intensity == "T-pace":
            # T-pace: 1min recovery per 5min work (20% ratio)
            target_recovery = work_duration * 0.2
            if recovery_duration < target_recovery * 0.7:  # Allow 30% tolerance
                ok = False
                issue = f"Recovery too short ({recovery_duration:.1f}min < {target_recovery:.1f}min recommended)"
                violations.append(
                    Violation(
                        type="T_PACE_RECOVERY_TOO_SHORT",
                        severity="LOW",
                        message=f"Recovery {idx} ({recovery_duration:.1f}min) below Daniels recommendation ({target_recovery:.1f}min)",
                        recommendation=f"Consider {target_recovery:.1f}min recovery (1min per 5min work)",
                    )
                )
        elif intensity == "R-pace":
            # R-pace: 2-3x recovery
            min_recovery = work_duration * 2.0
            max_recovery = work_duration * 3.0
            if recovery_duration < min_recovery:
                ok = False
                issue = f"Recovery too short ({recovery_duration:.1f}min < {min_recovery:.1f}min minimum)"
                violations.append(
                    Violation(
                        type="R_PACE_RECOVERY_TOO_SHORT",
                        severity="MODERATE",
                        message=f"Recovery {idx} ({recovery_duration:.1f}min) below R-pace minimum (2x work = {min_recovery:.1f}min)",
                        recommendation=f"Increase recovery to {min_recovery:.1f}-{max_recovery:.1f}min (2-3x work time)",
                    )
                )

        recovery_bout_analysis.append(
            RecoveryBout(
                duration_minutes=recovery_duration, type=recovery_type, ok=ok, issue=issue
            )
        )

    # Check total volume limits
    total_volume_ok = True
    if weekly_volume_km and total_work_km > 0:
        if intensity == "I-pace":
            max_ipace_km = min(10.0, weekly_volume_km * 0.08)
            if total_work_km > max_ipace_km:
                total_volume_ok = False
                violations.append(
                    Violation(
                        type="I_PACE_TOTAL_VOLUME_EXCEEDED",
                        severity="MODERATE",
                        message=f"Total I-pace volume ({total_work_km:.1f}km) exceeds safe limit ({max_ipace_km:.1f}km)",
                        recommendation=f"Reduce I-pace volume to ≤{max_ipace_km:.1f}km (lesser of 10km or 8% weekly)",
                    )
                )
        elif intensity == "T-pace":
            max_tpace_km = weekly_volume_km * 0.10
            if total_work_km > max_tpace_km:
                total_volume_ok = False
                violations.append(
                    Violation(
                        type="T_PACE_TOTAL_VOLUME_EXCEEDED",
                        severity="MODERATE",
                        message=f"Total T-pace volume ({total_work_km:.1f}km) exceeds safe limit ({max_tpace_km:.1f}km)",
                        recommendation=f"Reduce T-pace volume to ≤{max_tpace_km:.1f}km (10% of weekly volume)",
                    )
                )
        elif intensity == "R-pace":
            max_rpace_km = min(8.0, weekly_volume_km * 0.05)
            if total_work_km > max_rpace_km:
                total_volume_ok = False
                violations.append(
                    Violation(
                        type="R_PACE_TOTAL_VOLUME_EXCEEDED",
                        severity="MODERATE",
                        message=f"Total R-pace volume ({total_work_km:.1f}km) exceeds safe limit ({max_rpace_km:.1f}km)",
                        recommendation=f"Reduce R-pace volume to ≤{max_rpace_km:.1f}km (lesser of 8km or 5% weekly)",
                    )
                )

    # Daniels compliance: no violations = compliant
    daniels_compliance = len(violations) == 0

    # Generate recommendations if violations exist
    if not daniels_compliance:
        if intensity == "I-pace":
            recommendations.append("I-pace work: 3-5min bouts, equal recovery (jogging), total ≤10km or 8% weekly")
        elif intensity == "T-pace":
            recommendations.append("T-pace work: 5-15min bouts, 1min recovery per 5min work, total ≤10% weekly")
        elif intensity == "R-pace":
            recommendations.append("R-pace work: 30-90sec bouts, 2-3x recovery, total ≤8km or 5% weekly")

    return IntervalStructureValidation(
        workout_type=workout_type,
        intensity=intensity,
        work_bouts=work_bout_analysis,
        recovery_bouts=recovery_bout_analysis,
        violations=violations,
        total_work_volume_minutes=total_work_minutes,
        total_work_volume_km=total_work_km if total_work_km > 0 else None,
        total_volume_ok=total_volume_ok,
        daniels_compliance=daniels_compliance,
        recommendations=recommendations,
    )


# ============================================================================
# 2. Plan Structure Validation
# ============================================================================


def validate_plan_structure(
    total_weeks: int,
    goal_type: str,
    phases: Dict[str, int],  # phase_name -> num_weeks
    weekly_volumes_km: List[float],  # Week 1 to N volumes
    recovery_weeks: List[int],  # Week numbers designated as recovery
    race_week: Optional[int],  # Week number of race (optional for general_fitness)
) -> PlanStructureValidation:
    """Validate training plan structure for common errors.

    Checks:
    1. Phase duration appropriateness (base, build, peak, taper)
    2. Volume progression (10% rule - avg weekly increase ≤10%)
    3. Peak placement (2-3 weeks before race)
    4. Recovery week frequency (every 3-4 weeks)
    5. Taper structure (gradual volume reduction)

    Args:
        total_weeks: Total number of weeks in plan
        goal_type: Goal race type (e.g., "5k", "10k", "half_marathon", "marathon")
        phases: Dict mapping phase name to number of weeks
        weekly_volumes_km: List of weekly volumes (index 0 = week 1)
        recovery_weeks: List of week numbers designated as recovery
        race_week: Week number of race

    Returns:
        PlanStructureValidation with quality score and violations
    """
    violations: List[Violation] = []
    recommendations: List[str] = []

    goal_type_normalized = goal_type.lower().replace("-", "_").replace(" ", "_")
    is_general_fitness = goal_type_normalized == "general_fitness"

    # Standard phase durations by goal type
    PHASE_STANDARDS = {
        "5k": {"base": (4, 8), "build": (4, 8), "peak": (2, 4), "taper": (1, 2)},
        "10k": {"base": (6, 10), "build": (6, 10), "peak": (3, 5), "taper": (2, 3)},
        "half_marathon": {"base": (8, 12), "build": (8, 12), "peak": (3, 5), "taper": (2, 3)},
        "marathon": {"base": (12, 16), "build": (12, 16), "peak": (4, 6), "taper": (2, 3)},
    }

    # Get standards for goal type (default to half_marathon if unknown)
    standards = PHASE_STANDARDS.get(goal_type, PHASE_STANDARDS["half_marathon"])

    # 1. Phase duration checks
    phase_checks: Dict[str, PhaseCheck] = {}
    for phase_name, weeks in phases.items():
        if is_general_fitness:
            phase_checks[phase_name] = PhaseCheck(
                weeks=weeks,
                appropriate=True,
                note="General fitness uses rolling cycles",
                issue=None,
            )
            continue

        if phase_name in standards:
            min_weeks, max_weeks = standards[phase_name]
            appropriate = min_weeks <= weeks <= max_weeks
            note = None
            issue = None

            if not appropriate:
                if weeks < min_weeks:
                    issue = f"Too short - recommend {min_weeks}-{max_weeks} weeks"
                    violations.append(
                        Violation(
                            type=f"{phase_name.upper()}_PHASE_TOO_SHORT",
                            severity="MODERATE",
                            message=f"{phase_name.capitalize()} phase ({weeks} weeks) below recommended minimum ({min_weeks} weeks)",
                            recommendation=f"Extend {phase_name} phase to {min_weeks}-{max_weeks} weeks for {goal_type}",
                        )
                    )
                else:
                    issue = f"Too long - recommend {min_weeks}-{max_weeks} weeks"
                    violations.append(
                        Violation(
                            type=f"{phase_name.upper()}_PHASE_TOO_LONG",
                            severity="LOW",
                            message=f"{phase_name.capitalize()} phase ({weeks} weeks) exceeds recommended maximum ({max_weeks} weeks)",
                            recommendation=f"Consider shortening {phase_name} phase to {min_weeks}-{max_weeks} weeks",
                        )
                    )
            else:
                note = f"Standard duration for {goal_type}"

            phase_checks[phase_name] = PhaseCheck(
                weeks=weeks, appropriate=appropriate, note=note, issue=issue
            )

    # 2. Volume progression check (10% rule)
    if len(weekly_volumes_km) >= 2:
        start_volume = weekly_volumes_km[0]
        peak_volume = max(weekly_volumes_km)
        peak_week_idx = weekly_volumes_km.index(peak_volume)
        weeks_to_peak = peak_week_idx + 1

        total_increase_pct = ((peak_volume - start_volume) / start_volume) * 100
        avg_weekly_increase_pct = total_increase_pct / weeks_to_peak if weeks_to_peak > 0 else 0
        safe = avg_weekly_increase_pct <= 10.0

        note = None
        if not safe:
            violations.append(
                Violation(
                    type="VOLUME_PROGRESSION_TOO_AGGRESSIVE",
                    severity="MODERATE",
                    message=f"Average weekly volume increase ({avg_weekly_increase_pct:.1f}%) exceeds 10% rule",
                    recommendation=f"Reduce progression rate or extend plan duration (safe max: 10% per week)",
                )
            )
            note = "Exceeds 10% rule - injury risk elevated"

        volume_progression_check = VolumeProgressionCheck(
            start_volume_km=start_volume,
            peak_volume_km=peak_volume,
            total_increase_pct=total_increase_pct,
            weeks_to_peak=weeks_to_peak,
            avg_weekly_increase_pct=avg_weekly_increase_pct,
            safe=safe,
            note=note,
        )
    else:
        volume_progression_check = VolumeProgressionCheck(
            start_volume_km=0,
            peak_volume_km=0,
            total_increase_pct=0,
            weeks_to_peak=0,
            avg_weekly_increase_pct=0,
            safe=True,
            note="Insufficient data for progression analysis",
        )

    # 3. Peak placement check (2-3 weeks before race)
    if is_general_fitness or race_week is None:
        peak_placement_check = PeakPlacementCheck(
            peak_week_number=0,
            weeks_before_race=0,
            appropriate=True,
            note="Not applicable for general fitness",
        )
    else:
        peak_week_number = weekly_volumes_km.index(max(weekly_volumes_km)) + 1
        weeks_before_race = race_week - peak_week_number
        peak_appropriate = 2 <= weeks_before_race <= 3
        peak_note = None

        if not peak_appropriate:
            if weeks_before_race < 2:
                violations.append(
                    Violation(
                        type="PEAK_TOO_CLOSE_TO_RACE",
                        severity="MODERATE",
                        message=f"Peak week {weeks_before_race} week(s) before race (recommend 2-3 weeks)",
                        recommendation="Move peak earlier to allow adequate taper",
                    )
                )
                peak_note = "Too close to race - insufficient taper"
            else:
                violations.append(
                    Violation(
                        type="PEAK_TOO_FAR_FROM_RACE",
                        severity="LOW",
                        message=f"Peak week {weeks_before_race} weeks before race (recommend 2-3 weeks)",
                        recommendation="Move peak closer to race to maintain fitness",
                    )
                )
                peak_note = "Too far from race - may lose peak fitness"
        else:
            peak_note = "Optimal peak placement (2-3 weeks before race)"

        peak_placement_check = PeakPlacementCheck(
            peak_week_number=peak_week_number,
            weeks_before_race=weeks_before_race,
            appropriate=peak_appropriate,
            note=peak_note,
        )

    # 4. Recovery week frequency check (every 3-4 weeks)
    if len(recovery_weeks) > 0:
        # Calculate gaps between recovery weeks
        sorted_recovery = sorted(recovery_weeks)
        gaps = [sorted_recovery[i + 1] - sorted_recovery[i] for i in range(len(sorted_recovery) - 1)]
        avg_gap = sum(gaps) / len(gaps) if gaps else 0
        frequency_str = f"every {avg_gap:.0f} weeks" if gaps else "insufficient data"
        appropriate = 3 <= avg_gap <= 4 if gaps else False

        if not appropriate and gaps:
            if avg_gap < 3:
                violations.append(
                    Violation(
                        type="RECOVERY_WEEKS_TOO_FREQUENT",
                        severity="LOW",
                        message=f"Recovery weeks every {avg_gap:.0f} weeks (recommend every 3-4 weeks)",
                        recommendation="Reduce recovery week frequency to every 3-4 weeks",
                    )
                )
            elif avg_gap > 4:
                violations.append(
                    Violation(
                        type="RECOVERY_WEEKS_TOO_INFREQUENT",
                        severity="MODERATE",
                        message=f"Recovery weeks every {avg_gap:.0f} weeks (recommend every 3-4 weeks)",
                        recommendation="Add more recovery weeks (every 3-4 weeks) to prevent overtraining",
                    )
                )

        recovery_week_check = RecoveryWeekCheck(
            recovery_weeks=recovery_weeks,
            frequency=frequency_str,
            appropriate=appropriate,
            note="Standard frequency for progressive training" if appropriate else None,
        )
    else:
        recovery_week_check = RecoveryWeekCheck(
            recovery_weeks=[],
            frequency="none",
            appropriate=False,
            note="No recovery weeks planned - consider adding every 3-4 weeks",
        )
        violations.append(
            Violation(
                type="NO_RECOVERY_WEEKS",
                severity="MODERATE",
                message="Plan contains no recovery weeks",
                recommendation="Add recovery weeks every 3-4 weeks to prevent overtraining",
            )
        )

    # 5. Taper structure check (gradual volume reduction)
    if is_general_fitness or race_week is None:
        taper_structure_check = TaperStructureCheck(
            taper_weeks=[],
            week_reductions={},
            appropriate=True,
            note="Not applicable for general fitness",
        )
    else:
        taper_weeks = [w for w in range(race_week - 2, race_week + 1) if w > 0 and w <= len(weekly_volumes_km)]
        week_reductions: Dict[int, float] = {}
        taper_appropriate = False
        taper_note = None

        if len(taper_weeks) >= 2:
            peak_vol = max(weekly_volumes_km)
            for week_num in taper_weeks:
                week_vol = weekly_volumes_km[week_num - 1]
                reduction_pct = (week_vol / peak_vol) * 100
                week_reductions[week_num] = reduction_pct

            # Standard 3-week taper: 70%, 50%, 30%
            # For 2-week taper: 60%, 30%
            if len(taper_weeks) == 3:
                target_reductions = {taper_weeks[0]: 70, taper_weeks[1]: 50, taper_weeks[2]: 30}
                taper_appropriate = all(
                    abs(week_reductions[w] - target_reductions[w]) <= 15 for w in taper_weeks
                )
                taper_note = "Standard 3-week taper (70%, 50%, 30%)" if taper_appropriate else "Taper reductions not aligned with standard"
            elif len(taper_weeks) == 2:
                target_reductions = {taper_weeks[0]: 60, taper_weeks[1]: 30}
                taper_appropriate = all(
                    abs(week_reductions[w] - target_reductions[w]) <= 15 for w in taper_weeks
                )
                taper_note = "Standard 2-week taper (60%, 30%)" if taper_appropriate else "Taper reductions not aligned with standard"

            if not taper_appropriate:
                violations.append(
                    Violation(
                        type="TAPER_STRUCTURE_SUBOPTIMAL",
                        severity="LOW",
                        message="Taper volume reductions not aligned with standard protocol",
                        recommendation="Use gradual taper: 3-week (70%, 50%, 30%) or 2-week (60%, 30%)",
                    )
                )

        taper_structure_check = TaperStructureCheck(
            taper_weeks=taper_weeks,
            week_reductions=week_reductions,
            appropriate=taper_appropriate,
            note=taper_note,
        )

    # Calculate overall quality score
    total_checks = 5  # phase, volume, peak, recovery, taper
    passed_checks = sum(
        [
            all(check.appropriate for check in phase_checks.values()),
            volume_progression_check.safe,
            peak_placement_check.appropriate,
            recovery_week_check.appropriate,
            taper_structure_check.appropriate,
        ]
    )
    overall_quality_score = int((passed_checks / total_checks) * 100)

    # Generate recommendations
    if overall_quality_score < 75:
        recommendations.append(f"Plan quality score: {overall_quality_score}/100 - review violations")
    if len(violations) > 0:
        recommendations.append(f"Address {len(violations)} violation(s) to improve plan structure")

    return PlanStructureValidation(
        total_weeks=total_weeks,
        goal_type=goal_type,
        phase_duration_check=phase_checks,
        volume_progression_check=volume_progression_check,
        peak_placement_check=peak_placement_check,
        recovery_week_check=recovery_week_check,
        taper_structure_check=taper_structure_check,
        violations=violations,
        overall_quality_score=overall_quality_score,
        recommendations=recommendations,
    )


# ============================================================================
# 3. Goal Feasibility Assessment
# ============================================================================


def assess_goal_feasibility(
    goal_type: str,
    goal_time_seconds: int,  # Goal time in seconds
    goal_date: date,
    current_vdot: Optional[int],  # Current VDOT (if available from recent race)
    current_ctl: float,
    vdot_for_goal: Optional[int] = None,  # VDOT required for goal time (calculated by caller if needed)
) -> GoalFeasibilityAssessment:
    """Assess goal feasibility based on VDOT and CTL.

    Determines if a goal is realistic given:
    - Current fitness (VDOT, CTL)
    - Required fitness for goal
    - Time available for training

    Args:
        goal_type: Race type (e.g., "5k", "10k", "half_marathon", "marathon")
        goal_time_seconds: Goal time in seconds
        goal_date: Race date
        current_vdot: Current VDOT (None if no recent race)
        current_ctl: Current CTL
        vdot_for_goal: VDOT required to achieve goal time (optional - calculated from VDOT tables)

    Returns:
        GoalFeasibilityAssessment with verdict and recommendations
    """
    # Recommended CTL by race type (based on training methodologies)
    RECOMMENDED_CTL = {
        "5k": 35.0,
        "10k": 40.0,
        "half_marathon": 50.0,
        "marathon": 60.0,
    }

    # Typical training duration by race type (in weeks)
    TYPICAL_TRAINING_DURATION = {
        "5k": "6-10 weeks",
        "10k": "8-12 weeks",
        "half_marathon": "12-16 weeks",
        "marathon": "16-20 weeks",
    }

    goal_description = f"{goal_type.replace('_', ' ').title()} {_format_time(goal_time_seconds)} on {goal_date}"

    # Current fitness
    equivalent_race_time = None
    recent_race_result = None
    if current_vdot:
        # Would need VDOT table lookup here - for now, placeholder
        equivalent_race_time = f"Estimated based on VDOT {current_vdot}"

    current_fitness = CurrentFitness(
        vdot=current_vdot,
        ctl=current_ctl,
        equivalent_race_time=equivalent_race_time,
        recent_race_result=recent_race_result,
    )

    # Goal fitness needed
    ctl_recommended = RECOMMENDED_CTL.get(goal_type, 45.0)
    ctl_gap = ctl_recommended - current_ctl
    vdot_gap = None
    if current_vdot and vdot_for_goal:
        vdot_gap = vdot_for_goal - current_vdot

    goal_fitness_needed = GoalFitnessNeeded(
        vdot_for_goal=vdot_for_goal,
        vdot_gap=vdot_gap,
        ctl_recommended=ctl_recommended,
        ctl_gap=ctl_gap,
    )

    # Time available
    weeks_until_race = (goal_date - date.today()).days // 7
    typical_duration = TYPICAL_TRAINING_DURATION.get(goal_type, "12-16 weeks")
    typical_min_weeks = int(typical_duration.split("-")[0])
    sufficient = weeks_until_race >= typical_min_weeks

    time_available = TimeAvailable(
        weeks_until_race=weeks_until_race,
        typical_training_duration=typical_duration,
        sufficient=sufficient,
    )

    # Feasibility analysis
    typical_vdot_gain_per_month = 1.5  # Realistic with consistent training
    vdot_improvement_needed = vdot_gap if vdot_gap else None
    vdot_improvement_pct = None
    months_needed = None
    buffer = None
    limiting_factor = None

    if current_vdot and vdot_for_goal and vdot_gap:
        vdot_improvement_pct = (vdot_gap / current_vdot) * 100
        months_needed = vdot_gap / typical_vdot_gain_per_month
        months_available = weeks_until_race / 4.33
        buffer = months_available - months_needed if months_needed else None

        if not sufficient:
            limiting_factor = "insufficient_time"
        elif vdot_gap > current_vdot * 0.15:  # >15% improvement
            limiting_factor = "large_vdot_gap"
        elif ctl_gap > 20:
            limiting_factor = "low_ctl"

    feasibility_analysis = FeasibilityAnalysis(
        vdot_improvement_needed=vdot_improvement_needed,
        vdot_improvement_pct=vdot_improvement_pct,
        typical_vdot_gain_per_month=typical_vdot_gain_per_month,
        months_needed=months_needed,
        months_available=weeks_until_race / 4.33,
        buffer=buffer,
        limiting_factor=limiting_factor,
    )

    # Determine feasibility verdict
    feasibility_verdict = "REALISTIC"
    confidence_level = "MODERATE"
    warnings: List[str] = []
    recommendations: List[str] = []

    if not sufficient:
        feasibility_verdict = "UNREALISTIC"
        confidence_level = "HIGH"
        warnings.append(f"Only {weeks_until_race} weeks available (typical: {typical_duration})")
        recommendations.append(f"Extend race date or choose shorter race distance")
    elif limiting_factor == "large_vdot_gap":
        feasibility_verdict = "AMBITIOUS"
        confidence_level = "MODERATE"
        warnings.append(f"Requires {vdot_improvement_pct:.0f}% VDOT improvement (challenging)")
        recommendations.append("Consider intermediate goal or extend timeline")
    elif limiting_factor == "low_ctl":
        feasibility_verdict = "AMBITIOUS_BUT_REALISTIC"
        confidence_level = "MODERATE"
        warnings.append(f"CTL needs to increase from {current_ctl:.0f} to {ctl_recommended:.0f}")
        recommendations.append("Focus on gradual volume buildup (10% rule)")
    elif buffer and buffer > 2:
        feasibility_verdict = "VERY_REALISTIC"
        confidence_level = "HIGH"
        recommendations.append(f"Ample time available ({buffer:.1f} months buffer)")
    elif buffer and buffer < 0:
        feasibility_verdict = "AMBITIOUS"
        confidence_level = "MODERATE"
        warnings.append(f"Tight timeline (need {abs(buffer):.1f} more months ideally)")
        recommendations.append("Adjust goal time or race date for better feasibility")

    # Generate specific recommendations
    if current_vdot:
        recommendations.append(f"Current VDOT: {current_vdot} → Goal VDOT: {vdot_for_goal} (requires {vdot_gap} point gain)")
    if ctl_gap > 0:
        recommendations.append(f"Build CTL from {current_ctl:.0f} to {ctl_recommended:.0f} over {weeks_until_race} weeks")

    # Alternative scenarios
    alternative_scenarios: List[AlternativeScenario] = []
    if vdot_for_goal and current_vdot and vdot_gap > 2:
        # Suggest more conservative goal (VDOT halfway to target)
        conservative_vdot = current_vdot + (vdot_gap // 2)
        alternative_scenarios.append(
            AlternativeScenario(
                adjusted_goal_time="Estimated based on VDOT " + str(conservative_vdot),
                vdot_needed=conservative_vdot,
                feasibility="REALISTIC",
                note=f"More conservative goal reduces pressure, higher success probability",
            )
        )

    return GoalFeasibilityAssessment(
        goal=goal_description,
        current_fitness=current_fitness,
        goal_fitness_needed=goal_fitness_needed,
        time_available=time_available,
        feasibility_verdict=feasibility_verdict,
        feasibility_analysis=feasibility_analysis,
        confidence_level=confidence_level,
        recommendations=recommendations,
        alternative_scenarios=alternative_scenarios,
        warnings=warnings,
    )


# ============================================================================
# Helper Functions
# ============================================================================


def _format_time(seconds: int) -> str:
    """Format seconds as HH:MM:SS or MM:SS."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"

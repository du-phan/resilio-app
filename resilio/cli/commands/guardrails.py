"""
resilio guardrails - Volume validation and recovery planning.

Validate training volumes against Daniels' constraints, check weekly progression,
validate long runs, calculate safe volume ranges, and generate recovery protocols
for breaks, races, and illness.
"""

from typing import Optional

import typer

from resilio.api.guardrails import (
    validate_quality_volume,
    validate_weekly_progression,
    validate_long_run_limits,
    validate_weekly_volume_feasibility,
    calculate_safe_volume_range,
    calculate_break_return_plan,
    calculate_masters_recovery,
    calculate_race_recovery,
    generate_illness_recovery_plan,
    analyze_weekly_progression_context,
)
from resilio.cli.errors import api_result_to_envelope, get_exit_code_from_envelope
from resilio.cli.output import output_json

# Create subcommand app
app = typer.Typer(help="Volume validation and recovery planning")


# ============================================================
# VOLUME VALIDATION COMMANDS
# ============================================================


@app.command(name="quality-volume")
def quality_volume_command(
    ctx: typer.Context,
    t_pace: float = typer.Option(
        ...,
        "--t-pace",
        help="Threshold pace volume in km"
    ),
    i_pace: float = typer.Option(
        ...,
        "--i-pace",
        help="Interval pace volume in km"
    ),
    r_pace: float = typer.Option(
        ...,
        "--r-pace",
        help="Repetition pace volume in km"
    ),
    weekly_volume: float = typer.Option(
        ...,
        "--weekly-volume",
        help="Total weekly mileage in km"
    ),
) -> None:
    """Validate T/I/R pace volumes against Daniels' hard constraints.

    Daniels' Rules:
    - T-pace: ≤ 10% of weekly mileage
    - I-pace: ≤ lesser of 10km OR 8% of weekly mileage
    - R-pace: ≤ lesser of 8km OR 5% of weekly mileage

    Examples:
        resilio guardrails quality-volume --t-pace 4.5 --i-pace 6.0 --r-pace 2.0 --weekly-volume 50.0
        resilio guardrails quality-volume --t-pace 3.0 --i-pace 4.0 --r-pace 2.0 --weekly-volume 50.0

    The command returns violations if any pace type exceeds safe limits.
    """
    # Call API
    result = validate_quality_volume(
        t_pace_km=t_pace,
        i_pace_km=i_pace,
        r_pace_km=r_pace,
        weekly_mileage_km=weekly_volume,
    )

    # Build success message
    if hasattr(result, 'overall_ok'):
        if result.overall_ok:
            msg = "All quality volumes within safe limits"
        else:
            violation_count = len(result.violations)
            msg = f"Quality volume validation: {violation_count} violation(s) found"
    else:
        msg = "Quality volume validation failed"

    # Convert to envelope
    envelope = api_result_to_envelope(result, success_message=msg)

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)


@app.command(name="progression")
def progression_command(
    ctx: typer.Context,
    previous: float = typer.Option(
        ...,
        "--previous",
        help="Previous week's volume in km"
    ),
    current: float = typer.Option(
        ...,
        "--current",
        help="Current week's planned volume in km"
    ),
) -> None:
    """Validate weekly volume progression using the 10% rule.

    The 10% rule: Weekly mileage should not increase by more than 10%
    from one week to the next to minimize injury risk.

    Examples:
        resilio guardrails progression --previous 40.0 --current 50.0
        resilio guardrails progression --previous 40.0 --current 44.0

    Returns:
        - ok: true/false - Whether progression is safe
        - increase_pct: Percentage increase
        - safe_max_km: Maximum safe volume based on 10% rule
        - recommendation: Suggested action if unsafe
    """
    # Call API
    result = validate_weekly_progression(
        previous_volume_km=previous,
        current_volume_km=current,
    )

    # Build success message
    if hasattr(result, 'ok'):
        if result.ok:
            increase = result.increase_pct
            msg = f"Weekly progression safe: {increase:.1f}% increase"
        else:
            msg = f"Weekly progression violates 10% rule: {result.increase_pct:.1f}% increase"
    else:
        msg = "Progression validation failed"

    # Convert to envelope
    envelope = api_result_to_envelope(result, success_message=msg)

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)


@app.command(name="analyze-progression")
def analyze_progression_command(
    ctx: typer.Context,
    previous: float = typer.Option(
        ...,
        "--previous",
        help="Previous week's volume in km"
    ),
    current: float = typer.Option(
        ...,
        "--current",
        help="Current week's planned volume in km"
    ),
    ctl: Optional[float] = typer.Option(
        None,
        "--ctl",
        help="Current chronic training load (optional, enables capacity analysis)"
    ),
    run_days: Optional[int] = typer.Option(
        None,
        "--run-days",
        help="Number of run days per week (optional, enables per-session analysis)"
    ),
    age: Optional[int] = typer.Option(
        None,
        "--age",
        help="Athlete age (optional, flags masters considerations)"
    ),
    recent_injury: bool = typer.Option(
        False,
        "--recent-injury",
        help="Flag if recent injury (<90 days ago)"
    ),
) -> None:
    """Analyze volume progression with rich context for AI coaching decisions.

    This command provides CONTEXT and INSIGHTS, not pass/fail decisions.
    Claude Code interprets the data using training methodology knowledge.

    Philosophy: CLI computes and classifies → AI coach decides.

    Returns rich context including:
    - Volume classification (low/medium/high)
    - Traditional 10% rule analysis (for reference)
    - Absolute load analysis (Pfitzinger per-session guideline)
    - CTL-based capacity context (if --ctl provided)
    - Risk factors (injury, age, large percentage increase)
    - Protective factors (small absolute load, adequate capacity)
    - Coaching considerations from training methodology

    Examples:
        # BG scenario: Low volume, small absolute increase
        resilio guardrails analyze-progression --previous 15 --current 20 --ctl 27 --run-days 4 --age 32

        # High volume scenario: Large absolute increase
        resilio guardrails analyze-progression --previous 60 --current 75 --ctl 55 --run-days 4

        # Masters athlete with recent injury
        resilio guardrails analyze-progression --previous 40 --current 46 --age 52 --recent-injury

    Output includes:
        - volume_context: Volume level classification with injury risk factor
        - traditional_10pct_rule: Traditional rule analysis (reference only)
        - absolute_load_analysis: Pfitzinger per-session analysis
        - athlete_context: CTL-based capacity analysis
        - risk_factors: Identified risk factors with severity
        - protective_factors: Factors that reduce injury risk
        - coaching_considerations: Methodology-based guidance
    """
    # Call API
    result = analyze_weekly_progression_context(
        previous_volume_km=previous,
        current_volume_km=current,
        current_ctl=ctl,
        run_days_per_week=run_days,
        athlete_age=age,
        recent_injury=recent_injury,
    )

    # Build success message
    if hasattr(result, 'volume_context'):
        volume_cat = result.volume_context.category
        increase_pct = result.increase_pct
        msg = f"Progression context analyzed: {volume_cat} volume, {increase_pct:.1f}% increase"
    else:
        msg = "Progression context analysis failed"

    # Convert to envelope
    envelope = api_result_to_envelope(result, success_message=msg)

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code (always 0 for context provision, not validation)
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)


@app.command(name="long-run")
def long_run_command(
    ctx: typer.Context,
    distance: float = typer.Option(
        ...,
        "--distance",
        help="Long run distance in km"
    ),
    duration: int = typer.Option(
        ...,
        "--duration",
        help="Long run duration in minutes"
    ),
    weekly_volume: float = typer.Option(
        ...,
        "--weekly-volume",
        help="Total weekly volume in km"
    ),
    pct_limit: float = typer.Option(
        30.0,
        "--pct-limit",
        help="Percentage limit (default 30%)"
    ),
    duration_limit: Optional[int] = typer.Option(
        None,
        "--duration-limit",
        help="Duration limit in minutes (default: profile max or 150)"
    ),
) -> None:
    """Validate long run against weekly volume and duration limits.

    Daniels/Pfitzinger guidelines:
    - Long run ≤ 25-30% of weekly volume
    - Long run ≤ 2.5 hours (150 minutes) for most runners

    Examples:
        resilio guardrails long-run --distance 18.0 --duration 135 --weekly-volume 50.0
        resilio guardrails long-run --distance 15.0 --duration 120 --weekly-volume 50.0 --pct-limit 30

    Returns:
        - pct_ok: Whether percentage is within limit
        - duration_ok: Whether duration is within limit
        - violations: List of specific violations with recommendations
    """
    # Call API
    resolved_duration_limit = duration_limit
    if resolved_duration_limit is None:
        try:
            from resilio.api.profile import get_profile, ProfileError
            profile_result = get_profile()
            if not isinstance(profile_result, ProfileError) and profile_result.constraints:
                resolved_duration_limit = profile_result.constraints.max_time_per_session_minutes
        except Exception:
            resolved_duration_limit = None
    if resolved_duration_limit is None:
        resolved_duration_limit = 150

    result = validate_long_run_limits(
        long_run_km=distance,
        long_run_duration_minutes=duration,
        weekly_volume_km=weekly_volume,
        pct_limit=pct_limit,
        duration_limit_minutes=resolved_duration_limit,
    )

    # Build success message
    if hasattr(result, 'overall_ok'):
        if result.overall_ok:
            msg = "Long run within safe limits"
        else:
            violation_count = len(result.violations)
            msg = f"Long run validation: {violation_count} violation(s) found"
    else:
        msg = "Long run validation failed"

    # Convert to envelope
    envelope = api_result_to_envelope(result, success_message=msg)

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)


@app.command(name="feasible-volume")
def feasible_volume_command(
    ctx: typer.Context,
    run_days: int = typer.Option(
        ...,
        "--run-days",
        help="Planned run days per week"
    ),
    max_session_minutes: int = typer.Option(
        ...,
        "--max-session-minutes",
        help="Max session duration in minutes"
    ),
    easy_pace_min_per_km: float = typer.Option(
        ...,
        "--easy-pace-min-per-km",
        help="Conservative easy pace in min/km (e.g., 6.5 for 6:30/km)"
    ),
    target_volume: Optional[float] = typer.Option(
        None,
        "--target-volume",
        help="Planned weekly volume in km (optional)"
    ),
) -> None:
    """Validate weekly volume feasibility based on session duration constraints.

    Calculates the maximum feasible weekly volume given run frequency,
    max session duration, and a conservative easy pace.

    Examples:
        resilio guardrails feasible-volume --run-days 2 --max-session-minutes 90 --easy-pace-min-per-km 6.5
        resilio guardrails feasible-volume --run-days 2 --max-session-minutes 90 --easy-pace-min-per-km 6.5 --target-volume 32
    """
    result = validate_weekly_volume_feasibility(
        run_days_per_week=run_days,
        max_time_per_session_minutes=max_session_minutes,
        easy_pace_min_per_km=easy_pace_min_per_km,
        target_volume_km=target_volume,
    )

    if hasattr(result, "overall_ok"):
        if result.overall_ok:
            msg = (
                f"Weekly volume feasible (max ≈ {result.max_weekly_volume_km:.1f}km)"
            )
        else:
            violation_count = len(result.violations)
            msg = f"Weekly volume infeasible: {violation_count} violation(s) found"
    else:
        msg = "Feasibility validation failed"

    envelope = api_result_to_envelope(result, success_message=msg)
    output_json(envelope)

    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)


@app.command(name="safe-volume")
def safe_volume_command(
    ctx: typer.Context,
    ctl: float = typer.Option(
        ...,
        "--ctl",
        help="Current chronic training load"
    ),
    priority: str = typer.Option(
        ...,
        "--priority",
        help="Running priority: primary (100% volume), equal (75% volume), secondary (50% volume)"
    ),
    goal: str = typer.Option(
        "fitness",
        "--goal",
        help="Race goal: 5k, 10k, half_marathon, marathon, fitness"
    ),
    age: Optional[int] = typer.Option(
        None,
        "--age",
        help="Age for masters adjustments (optional)"
    ),
    recent_volume: Optional[float] = typer.Option(
        None,
        "--recent-volume",
        help="Recent weekly running volume (km/week, last 4 weeks avg) - prevents dangerous jumps"
    ),
    run_days_per_week: Optional[int] = typer.Option(
        None,
        "--run-days-per-week",
        help="Number of run days per week - warns if target volume conflicts with minimum workout durations"
    ),
) -> None:
    """Calculate safe weekly volume range based on current fitness and goals.

    Based on CTL zones and training methodology recommendations.

    CTL-based volume recommendations:
    - <20 (Beginner): 15-25 km/week
    - 20-35 (Recreational): 25-40 km/week
    - 35-50 (Competitive): 40-65 km/week
    - >50 (Advanced): 55-80+ km/week

    Multi-sport priority adjustments:
    - PRIMARY: Standard volumes (100%) - running is main focus
    - EQUAL: Reduced 25% - running balanced with other sports
    - SECONDARY: Reduced 50% - maintenance only, other sport is primary

    IMPORTANT: If --recent-volume is provided, the recommendation will start near that
    volume to avoid dangerous jumps, even if CTL suggests higher capacity. Use this to
    prevent violating the 10% rule when recent running volume differs from overall CTL.

    Examples:
        # Single-sport runner
        resilio guardrails safe-volume --ctl 44.0 --priority primary --goal half_marathon --age 52

        # Multi-sport athlete (running balanced with climbing)
        resilio guardrails safe-volume --ctl 30.0 --priority equal --goal 10k --recent-volume 20.7

        # Runner maintaining fitness while focused on another sport
        resilio guardrails safe-volume --ctl 27.0 --priority secondary --goal fitness

    Returns:
        - ctl_zone: Fitness level category
        - recent_weekly_volume_km: Actual recent volume (if provided)
        - volume_gap_pct: Gap between recent volume and CTL recommendation
        - recommended_start_km: Recommended starting weekly volume
        - recommended_peak_km: Recommended peak weekly volume
        - recommendation: Structured guidance
    """
    # Validate priority value
    if priority.lower() not in ["primary", "equal", "secondary"]:
        raise typer.BadParameter(
            "priority must be 'primary', 'equal', or 'secondary'"
        )

    # Call API
    result = calculate_safe_volume_range(
        current_ctl=ctl,
        running_priority=priority,
        goal_type=goal,
        athlete_age=age,
        recent_weekly_volume_km=recent_volume,
        run_days_per_week=run_days_per_week,
    )

    # Build success message
    if hasattr(result, 'ctl_zone'):
        msg = f"Safe volume range calculated for {result.ctl_zone} athlete (CTL {ctl:.1f})"
    else:
        msg = "Safe volume calculation failed"

    # Convert to envelope
    envelope = api_result_to_envelope(result, success_message=msg)

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)


# ============================================================
# RECOVERY PLANNING COMMANDS
# ============================================================


@app.command(name="break-return")
def break_return_command(
    ctx: typer.Context,
    days: int = typer.Option(
        ...,
        "--days",
        help="Length of training break in days"
    ),
    ctl: float = typer.Option(
        ...,
        "--ctl",
        help="CTL before the break"
    ),
    cross_training: str = typer.Option(
        "none",
        "--cross-training",
        help="Cross-training level: none, light, moderate, heavy"
    ),
) -> None:
    """Generate return-to-training protocol per Daniels Table 9.2.

    Multi-sport context: Cross-training during break (cycling, climbing, swimming)
    reduces fitness loss and accelerates return to full training.

    Daniels' guidelines:
    - ≤5 days: 100% load, 100% VDOT
    - 6-28 days: 50% first half, 75% second half, 93-99% VDOT
    - >8 weeks: Structured multi-week (33%, 50%, 75%), 80-92% VDOT

    Examples:
        resilio guardrails break-return --days 21 --ctl 44.0 --cross-training moderate
        resilio guardrails break-return --days 3 --ctl 35.0

    Returns:
        - load_phase_1_pct: Load percentage for first half of return
        - load_phase_2_pct: Load percentage for second half
        - vdot_adjustment_pct: VDOT adjustment (95-100)
        - return_schedule: Week-by-week return plan
        - estimated_full_return_weeks: Weeks to full training
    """
    # Call API
    result = calculate_break_return_plan(
        break_days=days,
        pre_break_ctl=ctl,
        cross_training_level=cross_training,
    )

    # Build success message
    if hasattr(result, 'estimated_full_return_weeks'):
        weeks = result.estimated_full_return_weeks
        msg = f"Break return plan generated: {days} day break, {weeks} week return"
    else:
        msg = "Break return plan failed"

    # Convert to envelope
    envelope = api_result_to_envelope(result, success_message=msg)

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)


@app.command(name="masters-recovery")
def masters_recovery_command(
    ctx: typer.Context,
    age: int = typer.Option(
        ...,
        "--age",
        help="Athlete age"
    ),
    workout_type: str = typer.Option(
        ...,
        "--workout-type",
        help="Workout type: vo2max, tempo, long_run, race"
    ),
) -> None:
    """Calculate age-specific recovery adjustments (Pfitzinger).

    Masters athletes (45+) require longer recovery between hard efforts.
    This function provides evidence-based recovery adjustments by age bracket.

    Age brackets: 18-35 (base), 36-45 (+0-1 day), 46-55 (+1-2 days), 56+ (+2-3 days)

    Examples:
        resilio guardrails masters-recovery --age 52 --workout-type vo2max
        resilio guardrails masters-recovery --age 28 --workout-type tempo

    Returns:
        - age_bracket: Age category
        - adjustments: Additional recovery days by workout type
        - recommended_recovery_days: Total recovery days by type
        - note: Additional guidance
    """
    # Call API
    result = calculate_masters_recovery(
        age=age,
        workout_type=workout_type,
    )

    # Build success message
    if hasattr(result, 'age_bracket'):
        msg = f"Masters recovery calculated for age {age} ({result.age_bracket})"
    else:
        msg = "Masters recovery calculation failed"

    # Convert to envelope
    envelope = api_result_to_envelope(result, success_message=msg)

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)


@app.command(name="race-recovery")
def race_recovery_command(
    ctx: typer.Context,
    distance: str = typer.Option(
        ...,
        "--distance",
        help="Race distance: 5k, 10k, half_marathon, marathon"
    ),
    age: int = typer.Option(
        ...,
        "--age",
        help="Athlete age"
    ),
    effort: str = typer.Option(
        "hard",
        "--effort",
        help="Effort level: easy, moderate, hard, max"
    ),
) -> None:
    """Determine post-race recovery protocol by distance and age.

    Multi-sport context: Cross-training (easy cycling, swimming) can be added
    earlier than running during recovery phase.

    Pfitzinger masters recovery tables:
    - 5K: 4-7 days
    - 10K: 6-10 days
    - Half Marathon: 7-14 days
    - Marathon: 14-28 days

    Examples:
        resilio guardrails race-recovery --distance half_marathon --age 52 --effort hard
        resilio guardrails race-recovery --distance 10k --age 28 --effort moderate

    Returns:
        - minimum_recovery_days: Minimum recovery needed
        - recommended_recovery_days: Recommended total recovery
        - quality_work_resume_day: Day to resume quality workouts
        - recovery_schedule: Day-by-day recovery guidance
    """
    # Call API
    result = calculate_race_recovery(
        race_distance=distance,
        athlete_age=age,
        finishing_effort=effort,
    )

    # Build success message
    if hasattr(result, 'minimum_recovery_days'):
        min_days = result.minimum_recovery_days
        msg = f"Race recovery plan generated: {distance.upper()} requires {min_days}+ days recovery"
    else:
        msg = "Race recovery calculation failed"

    # Convert to envelope
    envelope = api_result_to_envelope(result, success_message=msg)

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)


@app.command(name="illness-recovery")
def illness_recovery_command(
    ctx: typer.Context,
    start_date: str = typer.Option(
        ...,
        "--start-date",
        help="Illness start date (YYYY-MM-DD)"
    ),
    end_date: str = typer.Option(
        ...,
        "--end-date",
        help="Illness end date (YYYY-MM-DD)"
    ),
    severity: str = typer.Option(
        "moderate",
        "--severity",
        help="Illness severity: mild, moderate, severe"
    ),
) -> None:
    """Generate structured return-to-training plan after illness.

    Multi-sport context: Light cross-training (yoga, easy cycling) can resume
    before running during recovery phase.

    Conservative protocol: 1 day recovery per day sick (minimum).
    Monitor resting HR, fatigue levels, and symptoms before progression.

    Examples:
        resilio guardrails illness-recovery --start-date 2026-01-10 --end-date 2026-01-15 --severity moderate
        resilio guardrails illness-recovery --start-date 2026-01-01 --end-date 2026-01-03 --severity mild

    Returns:
        - illness_duration_days: Days of illness
        - estimated_ctl_drop: Expected CTL drop
        - return_protocol: Day-by-day return plan
        - full_training_resume_day: Day to resume full training
        - red_flags: Signs to stop training
    """
    # Call API
    result = generate_illness_recovery_plan(
        illness_start_date=start_date,
        illness_end_date=end_date,
        severity=severity,
    )

    # Build success message
    if hasattr(result, 'illness_duration_days'):
        duration = result.illness_duration_days
        resume_day = result.full_training_resume_day
        msg = f"Illness recovery plan: {duration} day illness, resume full training day {resume_day}"
    else:
        msg = "Illness recovery plan failed"

    # Convert to envelope
    envelope = api_result_to_envelope(result, success_message=msg)

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)

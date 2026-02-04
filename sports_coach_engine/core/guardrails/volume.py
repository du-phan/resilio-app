"""
Volume and load guardrail calculations.

Implements Daniels' Running Formula constraints on quality volume (T/I/R paces),
weekly progression (10% rule), and long run limits.
"""

from typing import Optional, Tuple
from sports_coach_engine.schemas.guardrails import (
    QualityVolumeValidation,
    WeeklyProgressionValidation,
    LongRunValidation,
    SafeVolumeRange,
    Violation,
    ViolationSeverity,
)


# ============================================================
# QUALITY VOLUME VALIDATION (DANIELS)
# ============================================================


def validate_quality_volume(
    t_pace_km: float,
    i_pace_km: float,
    r_pace_km: float,
    weekly_mileage_km: float,
) -> QualityVolumeValidation:
    """
    Validate T/I/R pace volumes against Daniels' hard constraints.

    Daniels' Rules:
    - T-pace: ≤ 10% of weekly mileage
    - I-pace: ≤ lesser of 10km OR 8% of weekly mileage
    - R-pace: ≤ lesser of 8km OR 5% of weekly mileage

    Args:
        t_pace_km: Total threshold pace volume in km
        i_pace_km: Total interval pace volume in km
        r_pace_km: Total repetition pace volume in km
        weekly_mileage_km: Total weekly mileage in km

    Returns:
        QualityVolumeValidation with limits, checks, and violations

    Example:
        >>> validation = validate_quality_volume(4.5, 6.0, 2.0, 50.0)
        >>> if not validation.overall_ok:
        ...     for v in validation.violations:
        ...         print(v.message)
    """
    violations = []

    # Threshold pace: ≤10% weekly
    t_pace_limit = weekly_mileage_km * 0.10
    t_pace_ok = t_pace_km <= t_pace_limit

    if not t_pace_ok:
        violations.append(
            Violation(
                type="T_PACE_VOLUME_EXCEEDED",
                severity=ViolationSeverity.MODERATE,
                message=f"T-pace volume ({t_pace_km:.1f}km) exceeds 10% weekly limit ({t_pace_limit:.1f}km)",
                current_value=t_pace_km,
                limit_value=t_pace_limit,
                recommendation=f"Reduce threshold session to {t_pace_limit:.1f}km total",
            )
        )

    # Interval pace: ≤ lesser of 10km OR 8% weekly
    i_pace_limit = min(10.0, weekly_mileage_km * 0.08)
    i_pace_ok = i_pace_km <= i_pace_limit

    if not i_pace_ok:
        violations.append(
            Violation(
                type="I_PACE_VOLUME_EXCEEDED",
                severity=ViolationSeverity.MODERATE,
                message=f"I-pace volume ({i_pace_km:.1f}km) exceeds safe limit ({i_pace_limit:.1f}km)",
                current_value=i_pace_km,
                limit_value=i_pace_limit,
                recommendation=(
                    f"Reduce interval session to {i_pace_limit:.1f}km "
                    f"(e.g., {int(i_pace_limit)}x1000m instead of {int(i_pace_km)}x1000m)"
                ),
            )
        )

    # Repetition pace: ≤ lesser of 8km OR 5% weekly
    r_pace_limit = min(8.0, weekly_mileage_km * 0.05)
    r_pace_ok = r_pace_km <= r_pace_limit

    if not r_pace_ok:
        violations.append(
            Violation(
                type="R_PACE_VOLUME_EXCEEDED",
                severity=ViolationSeverity.MODERATE,
                message=f"R-pace volume ({r_pace_km:.1f}km) exceeds safe limit ({r_pace_limit:.1f}km)",
                current_value=r_pace_km,
                limit_value=r_pace_limit,
                recommendation=f"Reduce repetition session to {r_pace_limit:.1f}km total",
            )
        )

    return QualityVolumeValidation(
        weekly_mileage_km=weekly_mileage_km,
        t_pace_volume_km=t_pace_km,
        t_pace_limit_km=t_pace_limit,
        t_pace_ok=t_pace_ok,
        i_pace_volume_km=i_pace_km,
        i_pace_limit_km=i_pace_limit,
        i_pace_ok=i_pace_ok,
        r_pace_volume_km=r_pace_km,
        r_pace_limit_km=r_pace_limit,
        r_pace_ok=r_pace_ok,
        violations=violations,
        overall_ok=t_pace_ok and i_pace_ok and r_pace_ok,
    )


# ============================================================
# WEEKLY PROGRESSION VALIDATION (10% RULE)
# ============================================================


def validate_weekly_progression(
    previous_volume_km: float,
    current_volume_km: float,
) -> WeeklyProgressionValidation:
    """
    Validate weekly volume progression using the 10% rule.

    The 10% rule: Weekly mileage should not increase by more than 10%
    from one week to the next to minimize injury risk.

    Args:
        previous_volume_km: Previous week's total volume
        current_volume_km: Current week's planned volume

    Returns:
        WeeklyProgressionValidation with increase analysis and safety check

    Example:
        >>> validation = validate_weekly_progression(40.0, 50.0)
        >>> if not validation.ok:
        ...     print(validation.recommendation)
    """
    increase_km = current_volume_km - previous_volume_km
    increase_pct = (increase_km / previous_volume_km * 100) if previous_volume_km > 0 else 0
    safe_max_km = previous_volume_km * 1.10  # 10% increase

    # Special case: First week (previous volume = 0)
    # 10% rule doesn't apply - any reasonable starting volume is safe
    if previous_volume_km == 0:
        return WeeklyProgressionValidation(
            previous_volume_km=previous_volume_km,
            current_volume_km=current_volume_km,
            increase_km=increase_km,
            increase_pct=0.0,  # No meaningful percentage from 0
            safe_max_km=current_volume_km,  # Use current as safe max
            ok=True,
            violation=None,
            recommendation=None,
        )

    # Decreases are always safe
    if increase_km <= 0:
        return WeeklyProgressionValidation(
            previous_volume_km=previous_volume_km,
            current_volume_km=current_volume_km,
            increase_km=increase_km,
            increase_pct=increase_pct,
            safe_max_km=safe_max_km,
            ok=True,
            violation=None,
            recommendation=None,
        )

    # Check if increase exceeds 10%
    ok = current_volume_km <= safe_max_km

    violation = None
    recommendation = None

    if not ok:
        violation = (
            f"Weekly volume increased by {increase_pct:.0f}% "
            f"(safe max: 10%, +{safe_max_km - previous_volume_km:.1f}km)"
        )
        recommendation = f"Reduce planned volume to {safe_max_km:.0f}km to stay within 10% rule"

    return WeeklyProgressionValidation(
        previous_volume_km=previous_volume_km,
        current_volume_km=current_volume_km,
        increase_km=increase_km,
        increase_pct=increase_pct,
        safe_max_km=safe_max_km,
        ok=ok,
        violation=violation,
        recommendation=recommendation,
    )


# ============================================================
# PROGRESSION CONTEXT ANALYSIS (RICH CONTEXT FOR AI COACHING)
# ============================================================


def analyze_weekly_progression_context(
    previous_volume_km: float,
    current_volume_km: float,
    current_ctl: Optional[float] = None,
    run_days_per_week: Optional[int] = None,
    athlete_age: Optional[int] = None,
    recent_injury: bool = False,
    injury_history: Optional[list] = None,
):
    """
    Analyze volume progression with rich context for AI coaching decisions.

    This function provides CONTEXT and INSIGHTS, not coaching decisions.
    Claude Code interprets this data using training methodology knowledge.

    Philosophy: CLI computes and classifies → AI coach decides.

    Args:
        previous_volume_km: Previous week's volume
        current_volume_km: Current week's planned volume
        current_ctl: Current CTL for capacity analysis
        run_days_per_week: Number of run days (for per-session analysis)
        athlete_age: Age for masters considerations
        recent_injury: Flag for recent injury (<90 days)
        injury_history: List of past injuries for pattern detection

    Returns:
        ProgressionContext with rich data for intelligent coaching

    Example:
        >>> context = analyze_weekly_progression_context(
        ...     previous_volume_km=15.0,
        ...     current_volume_km=20.0,
        ...     current_ctl=27.0,
        ...     run_days_per_week=4
        ... )
        >>> # Claude Code interprets volume_context, protective_factors, etc.
    """
    from sports_coach_engine.schemas.guardrails import (
        ProgressionContext,
        VolumeCategory,
        AbsoluteLoadAnalysis,
        AthleteCapacityContext,
        RiskFactor,
        ProtectiveFactor,
    )

    # ============================================================
    # 1. Calculate basic metrics
    # ============================================================
    increase_km = current_volume_km - previous_volume_km
    increase_pct = (increase_km / previous_volume_km * 100) if previous_volume_km > 0 else 0

    # ============================================================
    # 2. Classify volume level (low/medium/high)
    # ============================================================
    if current_volume_km < 25:
        volume_context = VolumeCategory(
            category="low",
            threshold_km="<25km",
            description="Low volume where absolute load per session is primary injury risk factor",
            injury_risk_factor="absolute_load",
        )
    elif current_volume_km < 50:
        volume_context = VolumeCategory(
            category="medium",
            threshold_km="25-50km",
            description="Medium volume where both absolute and cumulative load matter",
            injury_risk_factor="both",
        )
    else:
        volume_context = VolumeCategory(
            category="high",
            threshold_km="≥50km",
            description="High volume where cumulative load is primary injury risk factor",
            injury_risk_factor="cumulative_load",
        )

    # ============================================================
    # 3. Traditional 10% rule (for reference)
    # ============================================================
    safe_max_km = previous_volume_km * 1.10
    exceeds_by_pct = ((current_volume_km - safe_max_km) / safe_max_km * 100) if safe_max_km > 0 else 0

    traditional_10pct_rule = {
        "safe_max_km": round(safe_max_km, 1),
        "exceeds_by_pct": round(exceeds_by_pct, 1) if exceeds_by_pct > 0 else 0,
        "note": "Traditional rule applies uniformly regardless of volume level",
    }

    # ============================================================
    # 4. Absolute load analysis (Pfitzinger principle)
    # ============================================================
    per_session_increase_km = None
    within_pfitzinger_guideline = None
    if run_days_per_week and run_days_per_week > 0:
        per_session_increase_km = increase_km / run_days_per_week
        within_pfitzinger_guideline = per_session_increase_km <= 1.6

    # Assessment based on absolute load
    if per_session_increase_km is not None:
        if within_pfitzinger_guideline:
            assessment = f"Within safe absolute load guidelines ({per_session_increase_km:.2f}km/session ≤ 1.6km)"
        else:
            assessment = f"Exceeds Pfitzinger guideline ({per_session_increase_km:.2f}km/session > 1.6km)"
    else:
        assessment = f"Absolute increase of {increase_km:.1f}km (run days not provided for per-session analysis)"

    absolute_load_analysis = AbsoluteLoadAnalysis(
        increase_km=round(increase_km, 1),
        per_session_increase_km=round(per_session_increase_km, 2) if per_session_increase_km else None,
        pfitzinger_guideline_km=1.6,
        within_pfitzinger_guideline=within_pfitzinger_guideline,
        assessment=assessment,
    )

    # ============================================================
    # 5. Athlete capacity context (CTL-based)
    # ============================================================
    ctl_zone = None
    ctl_based_capacity_km = None
    target_within_capacity = None

    if current_ctl is not None:
        if current_ctl < 20:
            ctl_zone = "beginner"
            ctl_based_capacity_km = (15, 25)
        elif current_ctl < 35:
            ctl_zone = "recreational"
            ctl_based_capacity_km = (25, 40)
        elif current_ctl < 50:
            ctl_zone = "competitive"
            ctl_based_capacity_km = (40, 65)
        else:
            ctl_zone = "advanced"
            ctl_based_capacity_km = (55, 80)

        target_within_capacity = (
            ctl_based_capacity_km[0] <= current_volume_km <= ctl_based_capacity_km[1]
        )

    athlete_context = AthleteCapacityContext(
        ctl=current_ctl,
        ctl_zone=ctl_zone,
        ctl_based_capacity_km=ctl_based_capacity_km,
        target_within_capacity=target_within_capacity,
    )

    # ============================================================
    # 6. Identify risk factors
    # ============================================================
    risk_factors = []

    if recent_injury:
        risk_factors.append(
            RiskFactor(
                factor="Recent injury (<90 days)",
                severity="moderate",
                recommendation="Monitor discomfort levels and be prepared to adjust volume if symptoms return",
            )
        )

    if athlete_age and athlete_age >= 50:
        risk_factors.append(
            RiskFactor(
                factor=f"Masters athlete (age {athlete_age})",
                severity="low" if athlete_age < 60 else "moderate",
                recommendation="Masters athletes require longer recovery; consider conservative volume progression",
            )
        )

    # High percentage increase is a risk factor (but not a decision)
    if increase_pct > 20:
        risk_factors.append(
            RiskFactor(
                factor=f"Large percentage increase ({increase_pct:.0f}%)",
                severity="moderate" if increase_pct < 30 else "high",
                recommendation="Large percentage increases elevate injury risk; verify absolute load is manageable",
            )
        )

    # ============================================================
    # 7. Identify protective factors
    # ============================================================
    protective_factors = []

    if volume_context.category == "low" and increase_km < 10:
        protective_factors.append(
            ProtectiveFactor(
                factor="Low volume level with small absolute increase",
                note="At low volumes, small absolute increases are physiologically manageable despite high percentages",
            )
        )

    if target_within_capacity:
        protective_factors.append(
            ProtectiveFactor(
                factor="Target volume within CTL capacity",
                note=f"Target {current_volume_km:.0f}km is within fitness-based capacity range ({ctl_based_capacity_km[0]}-{ctl_based_capacity_km[1]}km)",
            )
        )

    if within_pfitzinger_guideline:
        protective_factors.append(
            ProtectiveFactor(
                factor="Within Pfitzinger per-session guideline",
                note=f"Per-session increase ({per_session_increase_km:.2f}km) is below recommended 1.6km limit",
            )
        )

    # ============================================================
    # 8. Coaching considerations (methodology guidance)
    # ============================================================
    coaching_considerations = []

    if volume_context.category == "low":
        coaching_considerations.append(
            "Low volume allows more flexible percentage increases when absolute load per session is small"
        )
        coaching_considerations.append(
            "Pfitzinger principle: '1.6km per session' often more relevant than 10% rule at low volumes"
        )

    if volume_context.category == "high":
        coaching_considerations.append(
            "High volume requires stricter adherence to 10% rule due to cumulative load stress"
        )
        coaching_considerations.append(
            "Large absolute increases (>10km) significantly increase injury risk"
        )

    if recent_injury:
        coaching_considerations.append(
            "Recent injury history warrants conservative approach; monitor response carefully"
        )

    if athlete_age and athlete_age >= 50:
        coaching_considerations.append(
            "Masters athletes benefit from more conservative progressions (Pfitzinger: reduce volume 10% for age 50+)"
        )

    # ============================================================
    # 9. Methodology references
    # ============================================================
    methodology_references = [
        "docs/training_books/advanced_marathoning_pete_pfitzinger.md - Volume progression guidelines",
        "docs/training_books/daniel_running_formula.md - 10% rule and volume management",
        "docs/coaching/methodology.md - Volume progression and guardrails section",
    ]

    # ============================================================
    # Return complete context
    # ============================================================
    return ProgressionContext(
        previous_volume_km=previous_volume_km,
        current_volume_km=current_volume_km,
        increase_km=round(increase_km, 1),
        increase_pct=round(increase_pct, 1),
        volume_context=volume_context,
        traditional_10pct_rule=traditional_10pct_rule,
        absolute_load_analysis=absolute_load_analysis,
        athlete_context=athlete_context,
        risk_factors=risk_factors,
        protective_factors=protective_factors,
        coaching_considerations=coaching_considerations,
        methodology_references=methodology_references,
    )


# ============================================================
# LONG RUN VALIDATION
# ============================================================


def validate_long_run_limits(
    long_run_km: float,
    long_run_duration_minutes: int,
    weekly_volume_km: float,
    pct_limit: float = 30.0,
    duration_limit_minutes: int = 150,
) -> LongRunValidation:
    """
    Validate long run against weekly volume and duration limits.

    Daniels/Pfitzinger guidelines:
    - Long run ≤ 25-30% of weekly volume
    - Long run ≤ 2.5 hours (150 minutes) for most runners

    Args:
        long_run_km: Long run distance in km
        long_run_duration_minutes: Expected long run duration
        weekly_volume_km: Total weekly volume
        pct_limit: Percentage limit (default 30%)
        duration_limit_minutes: Duration limit (default 150 min)

    Returns:
        LongRunValidation with checks and violations

    Example:
        >>> validation = validate_long_run_limits(18.0, 135, 50.0)
        >>> if not validation.overall_ok:
        ...     for v in validation.violations:
        ...         print(v.message)
    """
    violations = []

    # Check percentage of weekly volume
    pct_of_weekly = (long_run_km / weekly_volume_km * 100) if weekly_volume_km > 0 else 0
    pct_ok = pct_of_weekly <= pct_limit

    if not pct_ok:
        safe_max_km = weekly_volume_km * (pct_limit / 100)
        violations.append(
            Violation(
                type="LONG_RUN_EXCEEDS_WEEKLY_PCT",
                severity=ViolationSeverity.MODERATE,
                message=(
                    f"Long run ({long_run_km:.0f}km) is {pct_of_weekly:.0f}% of weekly volume "
                    f"(safe max: {pct_limit:.0f}%)"
                ),
                current_value=pct_of_weekly,
                limit_value=pct_limit,
                recommendation=(
                    f"Reduce long run to {safe_max_km:.0f}km or "
                    f"increase weekly volume to {long_run_km / (pct_limit / 100):.0f}km"
                ),
            )
        )

    # Check duration limit
    duration_ok = long_run_duration_minutes <= duration_limit_minutes

    if not duration_ok:
        violations.append(
            Violation(
                type="LONG_RUN_EXCEEDS_DURATION",
                severity=ViolationSeverity.MODERATE,
                message=(
                    f"Long run duration ({long_run_duration_minutes}min) exceeds "
                    f"recommended limit ({duration_limit_minutes}min)"
                ),
                current_value=float(long_run_duration_minutes),
                limit_value=float(duration_limit_minutes),
                recommendation=(
                    f"Reduce long run to {duration_limit_minutes}min "
                    f"(Daniels: most runners benefit from ≤2.5 hours)"
                ),
            )
        )

    return LongRunValidation(
        long_run_km=long_run_km,
        long_run_duration_minutes=long_run_duration_minutes,
        weekly_volume_km=weekly_volume_km,
        pct_of_weekly=pct_of_weekly,
        pct_limit=pct_limit,
        pct_ok=pct_ok,
        duration_limit_minutes=duration_limit_minutes,
        duration_ok=duration_ok,
        violations=violations,
        overall_ok=pct_ok and duration_ok,
    )


# ============================================================
# SAFE VOLUME RANGE CALCULATION
# ============================================================


def calculate_safe_volume_range(
    current_ctl: float,
    goal_type: str = "fitness",
    athlete_age: Optional[int] = None,
    recent_weekly_volume_km: Optional[float] = None,
    run_days_per_week: Optional[int] = None,
) -> SafeVolumeRange:
    """
    Calculate safe weekly volume range based on current fitness and goals.

    Based on CTL zones and training methodology recommendations.

    CTL-based volume recommendations:
    - <20 (Beginner): 15-25 km/week
    - 20-35 (Recreational): 25-40 km/week
    - 35-50 (Competitive): 40-65 km/week
    - >50 (Advanced): 55-80+ km/week

    CRITICAL: If recent_weekly_volume_km is provided, this function will recommend
    starting at or near that volume to avoid dangerous jumps, even if CTL suggests
    the athlete could handle more. The 10% rule applies to running-specific volume,
    not just overall fitness (CTL includes all sports).

    Args:
        current_ctl: Current chronic training load
        goal_type: Race goal ("5k", "10k", "half_marathon", "marathon", "fitness")
        athlete_age: Age for masters adjustments (optional)
        recent_weekly_volume_km: Actual recent running volume (last 4 weeks avg) (optional)

    Returns:
        SafeVolumeRange with recommendations

    Example:
        >>> # With recent volume data
        >>> range_info = calculate_safe_volume_range(27.0, "marathon", recent_weekly_volume_km=18.0)
        >>> # Recommends starting at ~18km, not 32km (CTL-based), to avoid 78% jump
    """
    # Determine CTL zone and base volume range
    if current_ctl < 20:
        ctl_zone = "beginner"
        base_range = (15, 25)
    elif current_ctl < 35:
        ctl_zone = "recreational"
        base_range = (25, 40)
    elif current_ctl < 50:
        ctl_zone = "competitive"
        base_range = (40, 65)
    else:
        ctl_zone = "advanced"
        base_range = (55, 80)

    # Normalize goal type
    normalized_goal = goal_type.lower().replace("-", "_").replace(" ", "_")
    if normalized_goal == "general_fitness":
        normalized_goal = "fitness"

    # Adjust for goal type
    goal_adjustments = {
        "5k": 0.9,  # Slightly lower volume for 5K
        "10k": 1.0,  # Base volume
        "half_marathon": 1.15,  # 15% higher for half
        "marathon": 1.3,  # 30% higher for marathon
        "fitness": 1.0,  # Base volume
    }

    adjustment_factor = goal_adjustments.get(normalized_goal, 1.0)
    goal_adjusted_range = (
        int(base_range[0] * adjustment_factor),
        int(base_range[1] * adjustment_factor),
    )

    # Masters adjustment (reduce 10% for 50+)
    masters_adjusted_range = None
    if athlete_age and athlete_age >= 50:
        masters_factor = 0.9
        masters_adjusted_range = (
            int(goal_adjusted_range[0] * masters_factor),
            int(goal_adjusted_range[1] * masters_factor),
        )

    # Recommendations
    final_range = masters_adjusted_range if masters_adjusted_range else goal_adjusted_range
    ctl_based_start = final_range[0]
    ctl_based_peak = final_range[1]

    # CRITICAL: Adjust for recent volume if provided
    volume_gap_pct = None
    if recent_weekly_volume_km is not None:
        # Calculate gap between recent volume and CTL-based recommendation
        volume_gap_pct = ((ctl_based_start - recent_weekly_volume_km) / recent_weekly_volume_km * 100)

        # If recent volume is significantly different, start there instead
        # Allow up to 10% increase from recent volume in first week
        if volume_gap_pct > 10:  # CTL suggests more than 10% jump
            recommended_start = int(recent_weekly_volume_km * 1.10)
            recommendation = (
                f"Start at {recommended_start}km/week (recent volume: {recent_weekly_volume_km:.0f}km), "
                f"build gradually to {ctl_based_peak}km. "
                f"⚠️ CTL suggests {ctl_based_start}km/week, but that's a {volume_gap_pct:.0f}% jump from recent training - "
                f"starting conservatively to avoid injury."
            )
        elif volume_gap_pct < -20:  # Recent volume way above CTL recommendation (detraining?)
            recommended_start = int(recent_weekly_volume_km * 0.95)
            recommendation = (
                f"Start at {recommended_start}km/week (recent volume: {recent_weekly_volume_km:.0f}km), "
                f"maintain consistency to rebuild CTL before increasing volume."
            )
        else:
            # Recent volume aligns with CTL recommendation
            recommended_start = int(recent_weekly_volume_km)
            recommendation = f"Start at {recommended_start}km/week, build to {ctl_based_peak}km over 8-12 weeks"

        recommended_peak = ctl_based_peak
    else:
        # No recent volume data - use CTL-based recommendation
        recommended_start = ctl_based_start
        recommended_peak = ctl_based_peak

        # Build recommendation string
        if masters_adjusted_range:
            recommendation = (
                f"Start at {recommended_start}km/week, build to {recommended_peak}km over 8-12 weeks. "
                f"Masters adjustment (age {athlete_age}): Reduced volume by 10% for recovery."
            )
        else:
            recommendation = f"Start at {recommended_start}km/week, build to {recommended_peak}km over 8-12 weeks"

    # Calculate minimum volume warning if run days are provided
    warning = None
    if run_days_per_week is not None and run_days_per_week > 0:
        # Standard minimums: 5 km easy run, 8 km long run
        # Minimum weekly volume = (N-1) × easy_min + long_min
        easy_min_km = 5
        long_min_km = 8
        minimum_weekly_km = (run_days_per_week - 1) * easy_min_km + long_min_km

        # Check if recommended start volume is below minimum
        if recommended_start < minimum_weekly_km:
            # Suggest reducing run days to make target achievable
            suggested_run_days = 3  # Start with 3 runs
            while suggested_run_days <= run_days_per_week:
                suggested_minimum = (suggested_run_days - 1) * easy_min_km + long_min_km
                if recommended_start >= suggested_minimum:
                    break
                suggested_run_days += 1

            if suggested_run_days <= run_days_per_week:
                warning = (
                    f"Target {recommended_start} km with {run_days_per_week} run days is below minimum "
                    f"({minimum_weekly_km} km). Suggest: {suggested_run_days} run days OR "
                    f"{minimum_weekly_km + 3} km target."
                )
            else:
                # Even 3 runs is too much for this volume
                warning = (
                    f"Target {recommended_start} km with {run_days_per_week} run days is below minimum "
                    f"({minimum_weekly_km} km). Suggest: Increase target to {minimum_weekly_km} km OR reduce run frequency."
                )

    return SafeVolumeRange(
        current_ctl=current_ctl,
        ctl_zone=ctl_zone,
        base_volume_range_km=base_range,
        goal_adjusted_range_km=goal_adjusted_range,
        masters_adjusted_range_km=masters_adjusted_range,
        recent_weekly_volume_km=recent_weekly_volume_km,
        volume_gap_pct=volume_gap_pct,
        recommended_start_km=recommended_start,
        recommended_peak_km=recommended_peak,
        recommendation=recommendation,
        warning=warning,
    )


# ============================================================
# MINIMUM WORKOUT DURATION/DISTANCE VALIDATION
# ============================================================

# Minimum workout durations (minutes)
EASY_RUN_MIN_DURATION = 30.0
LONG_RUN_MIN_DURATION = 60.0
TEMPO_MIN_DURATION = 40.0  # Including warmup/cooldown
INTERVALS_MIN_DURATION = 35.0  # Including warmup/cooldown

# Minimum distances (km)
EASY_RUN_MIN_DISTANCE = 5.0
LONG_RUN_MIN_DISTANCE = 8.0


def validate_workout_minimums(
    workout_type: str,
    duration_minutes: float,
    distance_km: Optional[float],
    profile: Optional[dict] = None,
) -> Optional[Violation]:
    """
    Validate workout meets minimum duration/distance requirements.

    Prevents unrealistically short workouts that don't provide adequate
    training stimulus (e.g., 22-minute easy runs).

    Minimums are inferred from athlete's historical patterns when available,
    falling back to conservative defaults only when no history exists.

    Default minimums (fallback):
    - Easy runs: ≥30 minutes OR ≥5 km
    - Long runs: ≥60 minutes OR ≥8 km
    - Tempo: ≥40 minutes (includes warmup/cooldown)
    - Intervals: ≥35 minutes (includes warmup/cooldown)

    Historical minimums (preferred):
    - Uses athlete's typical shortest workout for each type
    - Example: If athlete's easy runs typically 6-8km, enforce 5km minimum (80% of typical low end)

    Args:
        workout_type: Type of workout (easy, long_run, tempo, intervals, etc.)
        duration_minutes: Planned workout duration
        distance_km: Planned workout distance (if available)
        profile: Optional athlete profile with historical workout data

    Returns:
        Violation if minimums not met, None if valid

    Example:
        >>> profile = {"typical_easy_distance_km": 7.0, "typical_long_run_km": 10.0}
        >>> violation = validate_workout_minimums("easy", 22, 3.75, profile)
        >>> if violation:
        ...     print(violation.message)
        'Easy run distance (3.8km) below athlete's typical minimum (5.6km)'
    """
    # Rest days have no minimums
    if workout_type == "rest":
        return None

    # Determine minimums based on profile or defaults
    def get_minimum_duration(wtype: str) -> float:
        """Get minimum duration from profile or default."""
        if profile:
            # Try to get from profile (e.g., "typical_easy_duration_minutes")
            profile_key = f"typical_{wtype}_duration_minutes"
            if profile_key in profile and profile[profile_key]:
                # Use 80% of typical duration as minimum
                return profile[profile_key] * 0.8

        # Fallback to defaults
        defaults = {
            "easy": EASY_RUN_MIN_DURATION,
            "long_run": LONG_RUN_MIN_DURATION,
            "tempo": TEMPO_MIN_DURATION,
            "intervals": INTERVALS_MIN_DURATION,
        }
        return defaults.get(wtype, 30.0)

    def get_minimum_distance(wtype: str) -> float:
        """Get minimum distance from profile or default."""
        if profile:
            # Try to get from profile (e.g., "typical_easy_distance_km")
            profile_key = f"typical_{wtype}_distance_km"
            if profile_key in profile and profile[profile_key]:
                # Use 80% of typical distance as minimum
                return profile[profile_key] * 0.8

        # Fallback to defaults
        defaults = {
            "easy": EASY_RUN_MIN_DISTANCE,
            "long_run": LONG_RUN_MIN_DISTANCE,
        }
        return defaults.get(wtype, 5.0)

    min_duration = get_minimum_duration(workout_type)
    min_distance = get_minimum_distance(workout_type)

    # Determine message context (profile-based vs. default)
    context_msg = "athlete's typical minimum" if profile else "recommended minimum"

    # Check duration
    if duration_minutes < min_duration:
        workout_display = workout_type.replace("_", " ").title()
        return Violation(
            type=f"{workout_type.upper()}_TOO_SHORT",
            severity=ViolationSeverity.MODERATE,
            message=f"{workout_display} duration ({duration_minutes:.0f}min) below {context_msg} ({min_duration:.0f}min)",
            current_value=duration_minutes,
            limit_value=min_duration,
            recommendation=f"Increase duration to at least {min_duration:.0f}min for adequate training stimulus",
        )

    # Check distance if available (only for easy/long runs)
    if workout_type in ("easy", "long_run") and distance_km is not None:
        if distance_km < min_distance:
            workout_display = workout_type.replace("_", " ").title()
            return Violation(
                type=f"{workout_type.upper()}_TOO_SHORT",
                severity=ViolationSeverity.MODERATE,
                message=f"{workout_display} distance ({distance_km:.1f}km) below {context_msg} ({min_distance:.1f}km)",
                current_value=distance_km,
                limit_value=min_distance,
                recommendation=f"Increase distance to at least {min_distance:.1f}km",
            )

    return None

"""
Risk assessment calculations.

Implements current risk assessment, recovery window estimation,
training stress forecasting, and taper status tracking.
"""

from typing import List, Dict, Optional
from datetime import date, timedelta

from sports_coach_engine.schemas.analysis import (
    CurrentRiskAssessment,
    RecoveryWindowEstimate,
    TrainingStressForecast,
    TaperStatusAssessment,
    RiskLevel,
    RiskFactor,
    RiskOption,
    RecoveryCheckpoint,
    WeekForecast,
    RiskWindow,
    VolumeReductionCheck,
    TSBTrajectory,
    ReadinessTrend,
    TaperPhase,
)


# ============================================================
# CURRENT RISK ASSESSMENT
# ============================================================


def assess_current_risk(
    current_metrics: Dict,
    recent_activities: List[Dict],
    planned_workout: Optional[Dict] = None,
) -> CurrentRiskAssessment:
    """
    Holistic risk assessment combining all factors.

    Analyzes current metrics, recent training load, and planned workout
    to provide multi-factor injury risk assessment with actionable options.

    Args:
        current_metrics: Dict with ctl, atl, tsb, acwr, readiness
        recent_activities: List of recent activities (last 7 days)
        planned_workout: Optional planned workout dict

    Returns:
        CurrentRiskAssessment with risk level, contributing factors, and options

    Example:
        >>> metrics = {"acwr": 1.35, "readiness": 45, "tsb": -15}
        >>> risk = assess_current_risk(metrics, recent_activities, planned_workout)
        >>> print(f"Risk: {risk.overall_risk_level}, probability: {risk.injury_probability_pct}%")
    """
    # Extract metrics
    acwr = current_metrics.get("acwr", 1.0)
    readiness = current_metrics.get("readiness", 70)
    tsb = current_metrics.get("tsb", 0)
    ctl = current_metrics.get("ctl", 40)

    # Analyze contributing factors
    contributing_factors = []
    risk_score = 0.0  # Base score

    # ACWR factor
    if acwr > 1.5:
        contributing_factors.append(RiskFactor(
            name="ACWR_DANGER",
            value=acwr,
            threshold=1.5,
            severity="high",
            weight=0.40,
        ))
        risk_score += 0.40
    elif acwr > 1.3:
        contributing_factors.append(RiskFactor(
            name="ACWR_ELEVATED",
            value=acwr,
            threshold=1.3,
            severity="moderate",
            weight=0.30,
        ))
        risk_score += 0.20

    # Readiness factor
    if readiness < 35:
        contributing_factors.append(RiskFactor(
            name="READINESS_VERY_LOW",
            value=readiness,
            threshold=35,
            severity="high",
            weight=0.25,
        ))
        risk_score += 0.25
    elif readiness < 50:
        contributing_factors.append(RiskFactor(
            name="READINESS_LOW",
            value=readiness,
            threshold=50,
            severity="moderate",
            weight=0.20,
        ))
        risk_score += 0.15

    # TSB factor (overreached)
    if tsb < -25:
        contributing_factors.append(RiskFactor(
            name="TSB_OVERREACHED",
            value=tsb,
            threshold=-25,
            severity="high",
            weight=0.20,
        ))
        risk_score += 0.20

    # Recent lower-body load (check last 2 days)
    recent_lower_body = 0
    if recent_activities:
        for activity in recent_activities[-2:]:  # Last 2 days
            recent_lower_body += activity.get("lower_body_load_au", 0)

        # Dynamic threshold based on CTL
        safe_daily_lower = ctl * 2.5  # Rough heuristic
        if recent_lower_body > safe_daily_lower:
            contributing_factors.append(RiskFactor(
                name="RECENT_LOWER_BODY_LOAD",
                value=recent_lower_body,
                threshold=safe_daily_lower,
                severity="moderate",
                weight=0.25,
            ))
            risk_score += 0.15

    # Determine overall risk level
    injury_probability = min(100, risk_score * 100)  # Convert to percentage

    if risk_score >= 0.60:
        overall_risk = RiskLevel.DANGER
    elif risk_score >= 0.40:
        overall_risk = RiskLevel.HIGH
    elif risk_score >= 0.20:
        overall_risk = RiskLevel.MODERATE
    else:
        overall_risk = RiskLevel.LOW

    # Generate options
    options = []

    if planned_workout:
        # Option 1: Easy run (safest)
        easy_risk_reduction = min(60, risk_score * 50)
        options.append(RiskOption(
            action="easy_run_30min",
            risk_reduction_pct=easy_risk_reduction,
            description="Easy 30min run (safest)",
            pros=["Maintains aerobic stimulus", "ACWR stays manageable", "Lower injury risk"],
            cons=["Misses threshold/interval stimulus"],
        ))

        # Option 2: Move workout
        move_risk_reduction = min(40, risk_score * 35)
        options.append(RiskOption(
            action="move_to_tomorrow",
            risk_reduction_pct=move_risk_reduction,
            description="Move workout to tomorrow or later in week",
            pros=["Extra recovery day", "Full workout preserved"],
            cons=["Shifts weekly schedule"],
        ))

        # Option 3: Proceed as planned
        options.append(RiskOption(
            action="proceed_as_planned",
            risk_reduction_pct=0,
            description="Proceed with planned workout",
            pros=["Stays on schedule", f"Form is {'good' if tsb > -10 else 'moderate'} (TSB {tsb:.0f})"],
            cons=[f"{injury_probability:.0f}% injury risk"],
        ))
    else:
        # No planned workout
        options.append(RiskOption(
            action="rest_day",
            risk_reduction_pct=80,
            description="Take a rest day",
            pros=["Maximum recovery", "Metrics will improve"],
            cons=["Delays training progression"],
        ))

    # Rationale
    factor_names = ", ".join([f.name for f in contributing_factors])
    rationale = f"Risk factors: {factor_names}. " if contributing_factors else "No significant risk factors detected. "

    if overall_risk in [RiskLevel.HIGH, RiskLevel.DANGER]:
        rationale += "Multiple elevated risk factors warrant caution. "

    if recent_lower_body > 0:
        rationale += f"Recent lower-body load ({recent_lower_body:.0f} AU) may compound risk. "

    # Recommended action
    if overall_risk == RiskLevel.DANGER:
        recommended_action = "REST_OR_EASY_ONLY"
    elif overall_risk == RiskLevel.HIGH:
        recommended_action = "DOWNGRADE_OR_MOVE"
    elif overall_risk == RiskLevel.MODERATE:
        recommended_action = "PROCEED_WITH_CAUTION"
    else:
        recommended_action = "PROCEED_AS_PLANNED"

    recommendation = None
    if options:
        if overall_risk in [RiskLevel.HIGH, RiskLevel.DANGER]:
            recommendation = "Option 1 or 2 recommended based on risk level"
        elif overall_risk == RiskLevel.MODERATE:
            recommendation = "Option 2 or 3 based on athlete preference"

    return CurrentRiskAssessment(
        overall_risk_level=overall_risk,
        injury_probability_pct=round(injury_probability, 1),
        contributing_factors=contributing_factors,
        recommended_action=recommended_action,
        options=options,
        rationale=rationale.strip(),
        recommendation=recommendation,
    )


# ============================================================
# RECOVERY WINDOW ESTIMATION
# ============================================================


def estimate_recovery_window(
    trigger_type: str,
    current_value: float,
    safe_threshold: float,
) -> RecoveryWindowEstimate:
    """
    Estimate time until metric returns to safe zone.

    Calculates recovery timeline based on trigger type and provides
    day-by-day checklist for monitoring recovery progression.

    Args:
        trigger_type: Trigger identifier (e.g., "ACWR_ELEVATED", "TSB_OVERREACHED")
        current_value: Current metric value
        safe_threshold: Safe threshold value

    Returns:
        RecoveryWindowEstimate with min/typical/max days and monitoring checklist

    Example:
        >>> estimate = estimate_recovery_window("ACWR_ELEVATED", 1.35, 1.3)
        >>> print(f"Recovery: {estimate.estimated_recovery_days_typical} days typical")
    """
    # Recovery timelines by trigger type
    recovery_timelines = {
        "ACWR_ELEVATED": (2, 3, 5),  # min, typical, max days
        "ACWR_DANGER": (3, 5, 7),
        "TSB_OVERREACHED": (3, 5, 7),
        "READINESS_LOW": (1, 2, 3),
        "READINESS_VERY_LOW": (2, 4, 6),
    }

    min_days, typical_days, max_days = recovery_timelines.get(trigger_type, (2, 3, 5))

    # Build recovery checklist
    recovery_checklist = []

    if "ACWR" in trigger_type:
        recovery_checklist = [
            RecoveryCheckpoint(
                day=1,
                action="Rest or easy cross-training",
                check=f"ACWR should drop to ~{current_value - 0.03:.2f}",
            ),
            RecoveryCheckpoint(
                day=2,
                action="Easy 30min run",
                check=f"ACWR should drop to ~{safe_threshold + 0.02:.2f}",
            ),
            RecoveryCheckpoint(
                day=3,
                action="Check readiness",
                check="If readiness >70, safe to resume quality",
            ),
            RecoveryCheckpoint(
                day=typical_days,
                action="Resume quality work",
                check=f"ACWR should be <{safe_threshold:.2f}",
            ),
        ]
    elif "TSB" in trigger_type:
        recovery_checklist = [
            RecoveryCheckpoint(
                day=1,
                action="Complete rest",
                check="Monitor resting HR and soreness",
            ),
            RecoveryCheckpoint(
                day=2,
                action="Easy 20-30min run",
                check="TSB should start climbing toward -15",
            ),
            RecoveryCheckpoint(
                day=typical_days,
                action="Easy run + strides",
                check="TSB should be >-15",
            ),
            RecoveryCheckpoint(
                day=max_days,
                action="Resume normal training",
                check="TSB should be in -10 to +5 range",
            ),
        ]
    elif "READINESS" in trigger_type:
        recovery_checklist = [
            RecoveryCheckpoint(
                day=1,
                action="Rest or light cross-training",
                check="Monitor sleep quality and stress",
            ),
            RecoveryCheckpoint(
                day=typical_days,
                action="Easy run if readiness >50",
                check="Readiness should be improving",
            ),
            RecoveryCheckpoint(
                day=max_days,
                action="Resume normal training",
                check=f"Readiness should be >{safe_threshold:.0f}",
            ),
        ]

    monitoring_metrics = []
    if "ACWR" in trigger_type:
        monitoring_metrics = ["ACWR", "readiness", "lower_body_load"]
    elif "TSB" in trigger_type:
        monitoring_metrics = ["TSB", "ATL", "readiness"]
    elif "READINESS" in trigger_type:
        monitoring_metrics = ["readiness", "resting_hr"]

    note = "Recovery depends on athlete's rest quality and CTL trajectory"

    return RecoveryWindowEstimate(
        trigger=trigger_type,
        current_value=current_value,
        safe_threshold=safe_threshold,
        estimated_recovery_days_min=min_days,
        estimated_recovery_days_typical=typical_days,
        estimated_recovery_days_max=max_days,
        recovery_checklist=recovery_checklist,
        monitoring_metrics=monitoring_metrics,
        note=note,
    )


# ============================================================
# TRAINING STRESS FORECAST
# ============================================================


def forecast_training_stress(
    weeks_ahead: int,
    current_metrics: Dict,
    planned_weeks: List[Dict],
) -> TrainingStressForecast:
    """
    Project future CTL/ATL/TSB/ACWR based on planned training.

    Forecasts training stress metrics to identify future risk windows
    and suggest proactive plan adjustments.

    Args:
        weeks_ahead: Number of weeks to forecast (1-4)
        current_metrics: Current CTL, ATL, TSB values
        planned_weeks: List of planned week dicts with load_au

    Returns:
        TrainingStressForecast with week-by-week projections and risk windows

    Example:
        >>> forecast = forecast_training_stress(3, current_metrics, planned_weeks)
        >>> for week in forecast.forecast:
        ...     if week.risk_level == RiskLevel.MODERATE:
        ...         print(f"Week {week.week_number}: {week.warning}")
    """
    current_date_obj = date.today()
    current_ctl = current_metrics.get("ctl", 40.0)
    current_atl = current_metrics.get("atl", 45.0)

    forecast_weeks = []
    risk_windows = []

    # Simulate CTL/ATL progression
    ctl = current_ctl
    atl = current_atl

    for i in range(min(weeks_ahead, len(planned_weeks))):
        week = planned_weeks[i]
        week_number = week.get("week_number", i + 1)
        weekly_load = week.get("target_systemic_load_au", 0)

        # Simplified CTL/ATL calculation
        # Actual would use proper exponential weighted moving average
        ctl = ctl * 0.95 + weekly_load * 0.05  # 42-day time constant approximation
        atl = atl * 0.85 + weekly_load * 0.15  # 7-day time constant approximation

        tsb = ctl - atl
        acwr = atl / ctl if ctl > 0 else 1.0

        # Estimate readiness based on TSB and ACWR
        if tsb < -25 or acwr > 1.4:
            readiness_estimate = "low"
        elif tsb < -10 or acwr > 1.25:
            readiness_estimate = "moderate"
        else:
            readiness_estimate = "good"

        # Determine risk level
        if acwr > 1.4 or tsb < -25:
            risk_level = RiskLevel.HIGH
        elif acwr > 1.3 or tsb < -15:
            risk_level = RiskLevel.MODERATE
        else:
            risk_level = RiskLevel.LOW

        # Warning if elevated
        warning = None
        if risk_level in [RiskLevel.MODERATE, RiskLevel.HIGH]:
            if acwr > 1.3:
                warning = f"Week {week_number} shows elevated ACWR ({acwr:.2f}) - consider recovery week"
            elif tsb < -20:
                warning = f"Week {week_number} shows deep fatigue (TSB {tsb:.1f}) - consider reducing load"

        week_end = current_date_obj + timedelta(weeks=i + 1)

        week_forecast = WeekForecast(
            week_number=week_number,
            end_date=week_end,
            projected_ctl=round(ctl, 1),
            projected_atl=round(atl, 1),
            projected_tsb=round(tsb, 1),
            projected_acwr=round(acwr, 2),
            readiness_estimate=readiness_estimate,
            risk_level=risk_level,
            warning=warning,
        )
        forecast_weeks.append(week_forecast)

        # Track risk windows
        if risk_level in [RiskLevel.MODERATE, RiskLevel.HIGH]:
            risk_windows.append(RiskWindow(
                week_number=week_number,
                risk_level=risk_level,
                reason=f"Projected ACWR {acwr:.2f}" if acwr > 1.3 else f"Projected TSB {tsb:.1f}",
                recommendation="Consider reducing week volume by 20%" if risk_level == RiskLevel.HIGH else "Monitor closely",
            ))

    # Proactive adjustments
    proactive_adjustments = []
    if len(risk_windows) > 0:
        first_risk = risk_windows[0]
        proactive_adjustments.append(f"Add recovery week before Week {first_risk.week_number} to prevent fatigue spike")

        if first_risk.risk_level == RiskLevel.HIGH:
            proactive_adjustments.append(f"Reduce Week {first_risk.week_number} volume by 30%")

    return TrainingStressForecast(
        weeks_ahead=weeks_ahead,
        current_date=current_date_obj,
        forecast=forecast_weeks,
        risk_windows=risk_windows,
        proactive_adjustments=proactive_adjustments,
    )


# ============================================================
# TAPER STATUS ASSESSMENT
# ============================================================


def assess_taper_status(
    race_date: date,
    current_metrics: Dict,
    recent_weeks: List[Dict],
) -> TaperStatusAssessment:
    """
    Verify taper progression on track for race day.

    Analyzes volume reduction, TSB trajectory, and readiness trend
    to ensure optimal race-day freshness.

    Args:
        race_date: Upcoming race date
        current_metrics: Current CTL, ATL, TSB, readiness
        recent_weeks: List of recent week dicts with volume, load

    Returns:
        TaperStatusAssessment with volume/TSB/readiness checks and recommendations

    Example:
        >>> status = assess_taper_status(race_date, current_metrics, recent_weeks)
        >>> if status.overall_taper_status == "concern":
        ...     for flag in status.red_flags:
        ...         print(f"Warning: {flag}")
    """
    today = date.today()
    days_until_race = (race_date - today).days
    weeks_until_race = days_until_race // 7

    # Determine taper phase
    if weeks_until_race >= 3:
        taper_phase = TaperPhase.WEEK_3_OUT
    elif weeks_until_race == 2:
        taper_phase = TaperPhase.WEEK_2_OUT
    elif weeks_until_race <= 1 and days_until_race > 0:
        taper_phase = TaperPhase.RACE_WEEK
    else:
        taper_phase = TaperPhase.POST_RACE

    # Volume reduction check
    volume_checks = {}

    # Expected taper volumes: Week -3 (70%), Week -2 (50%), Race week (30%)
    if len(recent_weeks) >= 4:
        peak_volume = recent_weeks[-4].get("actual_volume_km", 50)  # 4 weeks ago = peak

        # Week -3
        if len(recent_weeks) >= 3:
            week_3_volume = recent_weeks[-3].get("actual_volume_km", 0)
            week_3_pct = (week_3_volume / peak_volume * 100) if peak_volume > 0 else 0
            volume_checks["week_minus_3"] = VolumeReductionCheck(
                week_label="week_minus_3",
                target_pct=70,
                actual_pct=int(week_3_pct),
                on_track=65 <= week_3_pct <= 75,
                status="on_track" if 65 <= week_3_pct <= 75 else "adjust_needed",
            )

        # Week -2
        if len(recent_weeks) >= 2:
            week_2_volume = recent_weeks[-2].get("actual_volume_km", 0)
            week_2_pct = (week_2_volume / peak_volume * 100) if peak_volume > 0 else 0
            volume_checks["week_minus_2"] = VolumeReductionCheck(
                week_label="week_minus_2",
                target_pct=50,
                actual_pct=int(week_2_pct),
                on_track=45 <= week_2_pct <= 55,
                status="on_track" if 45 <= week_2_pct <= 55 else "adjust_needed",
            )

        # Current week (if race week)
        if taper_phase == TaperPhase.RACE_WEEK:
            current_volume = recent_weeks[-1].get("actual_volume_km", 0) if recent_weeks else 0
            current_pct = (current_volume / peak_volume * 100) if peak_volume > 0 else 0
            volume_checks["current_week"] = VolumeReductionCheck(
                week_label="race_week",
                target_pct=30,
                actual_pct=int(current_pct) if current_volume > 0 else None,
                on_track=current_pct <= 35 if current_volume > 0 else True,
                status="in_progress",
            )

    # TSB trajectory
    current_tsb = current_metrics.get("tsb", 0)
    target_race_tsb_range = (5.0, 15.0)  # Standard race-ready range

    # Project race-day TSB (simplified - assumes linear progression)
    days_to_recover = days_until_race
    tsb_gain_per_day = 0.8  # Rough estimate
    projected_race_tsb = current_tsb + (days_to_recover * tsb_gain_per_day)

    tsb_on_track = target_race_tsb_range[0] <= projected_race_tsb <= target_race_tsb_range[1]

    tsb_trajectory = TSBTrajectory(
        current_tsb=current_tsb,
        target_race_day_tsb_range=target_race_tsb_range,
        projected_race_day_tsb=round(projected_race_tsb, 1),
        on_track=tsb_on_track,
    )

    # Readiness trend
    readiness_values = [w.get("avg_readiness", 70) for w in recent_weeks[-3:]]
    current_avg_readiness = readiness_values[-1] if readiness_values else 70

    trend = "improving"
    if len(readiness_values) >= 2:
        if readiness_values[-1] > readiness_values[0]:
            trend = "improving"
        elif readiness_values[-1] < readiness_values[0]:
            trend = "declining"
        else:
            trend = "stable"

    readiness_trend = ReadinessTrend(
        week_minus_3_avg=readiness_values[0] if len(readiness_values) >= 3 else None,
        week_minus_2_avg=readiness_values[1] if len(readiness_values) >= 2 else None,
        current_avg=current_avg_readiness,
        trend=trend,
        on_track=trend in ["improving", "stable"],
    )

    # Overall status
    all_checks_ok = (
        all(v.on_track for v in volume_checks.values())
        and tsb_on_track
        and readiness_trend.on_track
    )

    if all_checks_ok:
        overall_status = "on_track"
    elif any(v.status == "adjust_needed" for v in volume_checks.values()) or not tsb_on_track:
        overall_status = "concern"
    else:
        overall_status = "minor_adjustment_needed"

    # Recommendations
    recommendations = []
    if tsb_on_track:
        recommendations.append(f"TSB trajectory excellent - should peak at +{projected_race_tsb:.1f} on race day")
    else:
        if projected_race_tsb < target_race_tsb_range[0]:
            recommendations.append(f"TSB may be too low ({projected_race_tsb:.1f}) - reduce volume this week")
        else:
            recommendations.append(f"TSB may be too high ({projected_race_tsb:.1f}) - add short quality session")

    if readiness_trend.trend == "improving":
        recommendations.append("Readiness trending up - good sign")
    elif readiness_trend.trend == "declining":
        recommendations.append("Readiness declining - check sleep, nutrition, stress")

    recommendations.append("Maintain intensity in remaining workouts, reduce volume only")

    # Red flags
    red_flags = []
    if not tsb_on_track and projected_race_tsb < 0:
        red_flags.append("Projected race-day TSB is negative - insufficient recovery")

    if readiness_trend.trend == "declining":
        red_flags.append("Readiness declining during taper - investigate cause")

    return TaperStatusAssessment(
        race_date=race_date,
        weeks_until_race=weeks_until_race,
        taper_phase=taper_phase,
        volume_reduction_check=volume_checks,
        tsb_trajectory=tsb_trajectory,
        readiness_trend=readiness_trend,
        overall_taper_status=overall_status,
        recommendations=recommendations,
        red_flags=red_flags,
    )

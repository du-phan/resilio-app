"""
Weekly analysis calculations.

Implements intensity distribution validation (80/20 rule), activity gap
detection, multi-sport load analysis, and capacity checking.

Note: These functions provide the computational analysis logic. The API layer
handles data retrieval and integration with the persistence layer.
"""

from typing import List, Dict, Optional
from datetime import date, timedelta
from collections import defaultdict

from sports_coach_engine.schemas.analysis import (
    IntensityDistributionAnalysis,
    ActivityGapAnalysis,
    LoadDistributionAnalysis,
    WeeklyCapacityCheck,
    ActivityGap,
    ComplianceLevel,
)


# ============================================================
# INTENSITY DISTRIBUTION VALIDATION (80/20)
# ============================================================


def validate_intensity_distribution(
    activities: List[Dict],
    date_range_days: int = 28,
) -> IntensityDistributionAnalysis:
    """
    Validate intensity distribution against 80/20 rule (Fitzgerald).

    Analyzes intensity zones over a rolling window to check compliance
    with polarized training principles (80% low-intensity, 20% high-intensity).

    Args:
        activities: List of activity dicts with duration_minutes, intensity_zone
        date_range_days: Rolling window in days (default 28 for 4-week analysis)

    Returns:
        IntensityDistributionAnalysis with compliance level and recommendations

    Example:
        >>> activities = [{"duration_minutes": 60, "intensity_zone": "z2"}, ...]
        >>> analysis = validate_intensity_distribution(activities)
        >>> if analysis.compliance == ComplianceLevel.MODERATE_INTENSITY_RUT:
        ...     print("Too much Zone 3 training")
    """
    total_activities = len(activities)
    total_duration = sum(a.get("duration_minutes", 0) for a in activities)

    # Categorize intensity (simplified - actual would use HR zones)
    low_intensity_min = 0  # Zones 1-2
    moderate_intensity_min = 0  # Zone 3
    high_intensity_min = 0  # Zones 4-5

    for activity in activities:
        duration = activity.get("duration_minutes", 0)
        zone = activity.get("intensity_zone", "").lower()

        if zone in ["z1", "z2", "easy", "recovery"]:
            low_intensity_min += duration
        elif zone in ["z3", "moderate", "tempo_lower"]:
            moderate_intensity_min += duration
        elif zone in ["z4", "z5", "threshold", "interval", "repetition"]:
            high_intensity_min += duration
        else:
            # Default unknown to low intensity
            low_intensity_min += duration

    # Calculate percentages
    if total_duration > 0:
        low_pct = low_intensity_min / total_duration * 100
        moderate_pct = moderate_intensity_min / total_duration * 100
        high_pct = high_intensity_min / total_duration * 100
    else:
        low_pct = moderate_pct = high_pct = 0.0

    distribution = {
        "low_intensity_pct": round(low_pct, 1),
        "moderate_intensity_pct": round(moderate_pct, 1),
        "high_intensity_pct": round(high_pct, 1),
    }

    target_distribution = {
        "low_intensity_pct": 80.0,
        "moderate_intensity_pct": 0.0,  # Should minimize Zone 3
        "high_intensity_pct": 20.0,
    }

    # Determine compliance
    violations = []
    low_dev = abs(low_pct - 80.0)
    moderate_excess = moderate_pct
    high_dev = abs(high_pct - 20.0)

    # Compliance determination
    if moderate_pct > 15:
        compliance = ComplianceLevel.MODERATE_INTENSITY_RUT
        violations.append(f"Excessive moderate intensity ({moderate_pct:.0f}%) - 'gray zone' training")
    elif low_dev <= 5 and high_dev <= 5:
        compliance = ComplianceLevel.EXCELLENT
    elif low_dev <= 10 and high_dev <= 10:
        compliance = ComplianceLevel.GOOD
    elif low_dev <= 15 and high_dev <= 15:
        compliance = ComplianceLevel.FAIR
    else:
        compliance = ComplianceLevel.POOR

    # Violations
    if low_pct < 75:
        violations.append(f"Low-intensity too low ({low_pct:.0f}%, target 80%)")
    if high_pct < 15:
        violations.append(f"High-intensity too low ({high_pct:.0f}%, target 20%)")
    if high_pct > 25:
        violations.append(f"High-intensity too high ({high_pct:.0f}%, target 20%)")

    # Recommendations
    recommendations = []
    if low_pct < 80:
        recommendations.append(f"Slow down {(80 - low_pct) / 10:.0f}-{(80 - low_pct) / 5:.0f} easy runs per week - aim for RPE 3-4 max")
    if moderate_pct > 10:
        recommendations.append("Eliminate moderate-intensity 'gray zone' sessions (Zone 3)")
    if high_pct < 20:
        gap = 20 - high_pct
        recommendations.append(f"Add {gap / 5:.0f} more quality session(s) to reach 20% high-intensity")

    # Polarization score (0-100)
    polarization_score = max(0, min(100, int(100 - (low_dev + high_dev + moderate_pct * 2))))

    note = "80/20 validation only applies if running ≥3 days/week" if total_activities < 12 else None

    return IntensityDistributionAnalysis(
        date_range_days=date_range_days,
        total_activities=total_activities,
        total_duration_minutes=total_duration,
        distribution=distribution,
        target_distribution=target_distribution,
        compliance=compliance,
        violations=violations,
        recommendations=recommendations,
        polarization_score=polarization_score,
        note=note,
    )


# ============================================================
# ACTIVITY GAP DETECTION
# ============================================================


def detect_activity_gaps(
    activities: List[Dict],
    min_gap_days: int = 7,
) -> ActivityGapAnalysis:
    """
    Identify training breaks/gaps with context.

    Detects periods without training activity and analyzes potential
    causes, CTL impact, and recovery status.

    Args:
        activities: List of activity dicts with date, notes, etc.
        min_gap_days: Minimum gap duration to detect (default 7 days)

    Returns:
        ActivityGapAnalysis with detected gaps, patterns, and recommendations

    Example:
        >>> activities = [{"date": "2026-01-01", "ctl": 44}, {"date": "2026-01-20", "ctl": 30}]
        >>> analysis = detect_activity_gaps(activities, min_gap_days=7)
        >>> for gap in analysis.gaps:
        ...     print(f"Gap: {gap.duration_days} days, CTL dropped {gap.ctl_drop_pct}%")
    """
    if len(activities) < 2:
        return ActivityGapAnalysis(
            gaps=[],
            total_gaps=0,
            total_gap_days=0,
            patterns=[],
            recommendations=[],
        )

    # Sort activities by date
    sorted_activities = sorted(activities, key=lambda a: a.get("date", ""))

    gaps = []
    total_gap_days = 0

    for i in range(len(sorted_activities) - 1):
        current = sorted_activities[i]
        next_activity = sorted_activities[i + 1]

        current_date = date.fromisoformat(current.get("date", ""))
        next_date = date.fromisoformat(next_activity.get("date", ""))

        gap_days = (next_date - current_date).days - 1  # -1 to not count activity days themselves

        if gap_days >= min_gap_days:
            ctl_before = current.get("ctl")
            ctl_after = next_activity.get("ctl")
            ctl_drop_pct = None
            if ctl_before and ctl_after:
                ctl_drop_pct = (ctl_before - ctl_after) / ctl_before * 100 if ctl_before > 0 else 0.0

            # Detect potential cause from notes
            potential_cause = None
            evidence = []
            notes_text = (current.get("notes", "") + " " + next_activity.get("notes", "")).lower()
            if "injury" in notes_text or "injured" in notes_text or "pain" in notes_text:
                potential_cause = "injury"
                evidence.append("Injury-related keywords in notes")
            elif "sick" in notes_text or "ill" in notes_text or "flu" in notes_text:
                potential_cause = "illness"
                evidence.append("Illness-related keywords in notes")
            elif "travel" in notes_text or "vacation" in notes_text:
                potential_cause = "planned_break"
                evidence.append("Travel/vacation keywords in notes")

            gap = ActivityGap(
                start_date=current_date + timedelta(days=1),
                end_date=next_date - timedelta(days=1),
                duration_days=gap_days,
                ctl_before=ctl_before,
                ctl_after=ctl_after,
                ctl_drop_pct=round(ctl_drop_pct, 1) if ctl_drop_pct is not None else None,
                potential_cause=potential_cause,
                evidence=evidence,
            )
            gaps.append(gap)
            total_gap_days += gap_days

    # Pattern detection
    patterns = []
    if len(gaps) > 0:
        avg_gap = total_gap_days / len(gaps)
        patterns.append(f"{len(gaps)} gap(s) detected, average duration {avg_gap:.0f} days")

        injury_gaps = [g for g in gaps if g.potential_cause == "injury"]
        if len(injury_gaps) > 1:
            patterns.append(f"Multiple injury-related gaps detected - pattern suggests recurring injury risk")

    # Recommendations
    recommendations = []
    for gap in gaps:
        if gap.ctl_drop_pct and gap.ctl_drop_pct > 30:
            recommendations.append(f"CTL dropped {gap.ctl_drop_pct:.0f}% during {gap.duration_days}-day gap - use break return protocol")

        if gap.potential_cause == "injury":
            recommendations.append(f"Injury gap detected ({gap.start_date}) - review training load and recovery protocols")

    return ActivityGapAnalysis(
        gaps=gaps,
        total_gaps=len(gaps),
        total_gap_days=total_gap_days,
        patterns=patterns,
        recommendations=recommendations,
    )


# ============================================================
# LOAD DISTRIBUTION BY SPORT
# ============================================================


def analyze_load_distribution_by_sport(
    activities: List[Dict],
    date_range_days: int = 7,
    sport_priority: str = "equal",
) -> LoadDistributionAnalysis:
    """
    Analyze multi-sport load breakdown.

    Calculates systemic and lower-body load distribution across sports,
    checks adherence to sport priority preferences, and identifies fatigue risks.

    Args:
        activities: List of activity dicts with sport_type, systemic_load_au, lower_body_load_au
        date_range_days: Analysis window in days (default 7)
        sport_priority: Sport priority ("running_primary", "equal", "other_primary")

    Returns:
        LoadDistributionAnalysis with load breakdown and recommendations

    Example:
        >>> activities = [
        ...     {"sport_type": "run", "systemic_load_au": 200, "lower_body_load_au": 200},
        ...     {"sport_type": "climb", "systemic_load_au": 150, "lower_body_load_au": 30}
        ... ]
        >>> analysis = analyze_load_distribution_by_sport(activities)
        >>> print(f"Running: {analysis.systemic_load_by_sport['run']:.0f} AU")
    """
    # Aggregate loads by sport
    systemic_by_sport = defaultdict(float)
    lower_by_sport = defaultdict(float)

    for activity in activities:
        sport = activity.get("sport_type", "unknown")
        systemic_by_sport[sport] += activity.get("systemic_load_au", 0)
        lower_by_sport[sport] += activity.get("lower_body_load_au", 0)

    total_systemic = sum(systemic_by_sport.values())
    total_lower = sum(lower_by_sport.values())

    # Format with percentages
    systemic_load_by_sport = {
        sport: load
        for sport, load in systemic_by_sport.items()
    }

    lower_body_load_by_sport = {
        sport: load
        for sport, load in lower_by_sport.items()
    }

    # Sport priority adherence
    running_systemic_pct = (systemic_by_sport.get("run", 0) / total_systemic * 100) if total_systemic > 0 else 0.0

    # Define expected ranges per priority (from multi_sport_balance.md)
    PRIORITY_RANGES = {
        "primary": (60, 70),      # Running should be 60-70% of systemic load
        "equal": (40, 50),        # Running ~40-50% of systemic load
        "secondary": (25, 35),    # Running ~25-35% of systemic load
    }

    expected_range = PRIORITY_RANGES.get(sport_priority, (40, 60))  # Default to balanced
    running_pct = round(running_systemic_pct, 1)

    # Check if actual running % is within expected range for priority
    on_track = expected_range[0] <= running_pct <= expected_range[1]

    # Provide helpful context if off-track
    if not on_track:
        if running_pct > expected_range[1]:
            deviation = "running_heavy"
            note = f"Running is {running_pct}% of load (expected {expected_range[0]}-{expected_range[1]}% for {sport_priority.upper()} priority)"
        else:
            deviation = "running_light"
            note = f"Running is {running_pct}% of load (expected {expected_range[0]}-{expected_range[1]}% for {sport_priority.upper()} priority)"
    else:
        deviation = None
        note = f"Running load ({running_pct}%) aligns with {sport_priority.upper()} priority target"

    sport_priority_adherence = {
        "profile_priority": sport_priority,
        "expected_range_pct": expected_range,
        "actual_running_pct": running_pct,
        "on_track": on_track,
        "deviation": deviation,
        "note": note,
    }

    # Fatigue risk flags
    fatigue_risk_flags = []
    running_lower_pct = (lower_by_sport.get("run", 0) / total_lower * 100) if total_lower > 0 else 0.0
    if running_lower_pct > 80:
        fatigue_risk_flags.append(f"Lower-body load concentrated in running ({running_lower_pct:.0f}%)")

    # Check for high-load days that might interfere
    # (Simplified - actual would analyze day-by-day patterns)

    # Recommendations
    recommendations = []
    if running_lower_pct > 75 and len(systemic_by_sport) > 1:
        recommendations.append("Consider cross-training (cycling, swimming) to reduce lower-body impact while maintaining load")

    return LoadDistributionAnalysis(
        date_range_days=date_range_days,
        systemic_load_by_sport=systemic_load_by_sport,
        lower_body_load_by_sport=lower_body_load_by_sport,
        total_systemic_load=total_systemic,
        total_lower_body_load=total_lower,
        sport_priority_adherence=sport_priority_adherence,
        fatigue_risk_flags=fatigue_risk_flags,
        recommendations=recommendations,
    )


# ============================================================
# WEEKLY CAPACITY CHECK
# ============================================================


def check_weekly_capacity(
    week_number: int,
    planned_volume_km: float,
    planned_systemic_load_au: float,
    historical_max_volume_km: float,
    historical_max_systemic_load_au: float,
) -> WeeklyCapacityCheck:
    """
    Validate planned volume against proven capacity.

    Checks if planned training exceeds athlete's historically demonstrated
    capacity, identifies risk factors, and provides recommendations.

    Args:
        week_number: Week number in plan
        planned_volume_km: Planned weekly volume
        planned_systemic_load_au: Planned systemic load
        historical_max_volume_km: Historical maximum weekly volume
        historical_max_systemic_load_au: Historical maximum systemic load

    Returns:
        WeeklyCapacityCheck with capacity utilization and risk assessment

    Example:
        >>> check = check_weekly_capacity(15, 60.0, 550.0, 50.0, 480.0)
        >>> if check.exceeds_proven_capacity:
        ...     print(f"Plan exceeds capacity by {check.capacity_utilization_km - 100:.0f}%")
    """
    # Calculate capacity utilization
    capacity_util_km = (planned_volume_km / historical_max_volume_km * 100) if historical_max_volume_km > 0 else 0.0
    capacity_util_load = (planned_systemic_load_au / historical_max_systemic_load_au * 100) if historical_max_systemic_load_au > 0 else 0.0

    exceeds_capacity = capacity_util_km > 110 or capacity_util_load > 110  # 10% buffer

    # Risk assessment
    if capacity_util_km > 130 or capacity_util_load > 130:
        risk_level = "high"
    elif capacity_util_km > 110 or capacity_util_load > 110:
        risk_level = "moderate"
    else:
        risk_level = "low"

    # Risk factors
    risk_factors = []
    if capacity_util_km > 110:
        risk_factors.append(f"Planned volume ({planned_volume_km:.0f}km) exceeds historical max ({historical_max_volume_km:.0f}km) by {capacity_util_km - 100:.0f}%")

    if capacity_util_load > 110:
        risk_factors.append(f"Planned load ({planned_systemic_load_au:.0f} AU) exceeds historical max ({historical_max_systemic_load_au:.0f} AU) by {capacity_util_load - 100:.0f}%")

    if planned_volume_km > historical_max_volume_km:
        risk_factors.append(f"No evidence of sustaining >{historical_max_volume_km:.0f}km in activity history")

    # Recommendations
    recommendations = []
    if exceeds_capacity:
        safe_volume = historical_max_volume_km * 1.04  # 4% progressive overload
        recommendations.append(f"Reduce Week {week_number} volume to {safe_volume:.0f}km (historical max + 4%)")
        recommendations.append("Alternative: Add recovery week before attempting this volume")

    return WeeklyCapacityCheck(
        week_number=week_number,
        planned_volume_km=planned_volume_km,
        planned_systemic_load_au=planned_systemic_load_au,
        historical_max_volume_km=historical_max_volume_km,
        historical_max_systemic_load_au=historical_max_systemic_load_au,
        capacity_utilization_km=round(capacity_util_km, 1),
        capacity_utilization_load=round(capacity_util_load, 1),
        exceeds_proven_capacity=exceeds_capacity,
        risk_assessment=risk_level,
        risk_factors=risk_factors,
        recommendations=recommendations,
    )

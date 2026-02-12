"""
Pace adjustments for environmental conditions.

Implements pace adjustments for altitude, heat, humidity, and hills based on
exercise physiology research and Daniels' recommendations.
"""

from resilio.schemas.vdot import PaceAdjustment, ConditionType


# ============================================================
# ADJUSTMENT FUNCTIONS
# ============================================================


def adjust_pace_for_altitude(base_pace_sec_per_km: int, altitude_feet: float) -> PaceAdjustment:
    """Adjust pace for altitude.

    At altitude, VO2max decreases approximately 1-2% per 1000ft above 5000ft.
    E/L/T/I paces should be effort-based (use RPE/HR), not pace-based.
    R-pace can stay the same but requires more recovery.

    Args:
        base_pace_sec_per_km: Sea-level pace in seconds per km
        altitude_feet: Altitude in feet

    Returns:
        PaceAdjustment with recommendation
    """
    if altitude_feet < 3000:
        # Minimal effect below 3000ft
        return PaceAdjustment(
            base_pace_sec_per_km=base_pace_sec_per_km,
            adjusted_pace_sec_per_km=base_pace_sec_per_km,
            adjustment_seconds=0,
            condition_type=ConditionType.ALTITUDE,
            severity=altitude_feet,
            reason=f"Altitude ({altitude_feet:,.0f}ft) below significant threshold",
            recommendation="No pace adjustment needed",
        )

    # Calculate approximate adjustment (simplified model)
    # ~1.5% slower per 1000ft above 3000ft
    altitude_factor = (altitude_feet - 3000) / 1000.0
    slowdown_pct = altitude_factor * 1.5 / 100.0  # 1.5% per 1000ft

    # Apply adjustment
    adjustment_seconds = int(base_pace_sec_per_km * slowdown_pct)
    adjusted_pace = base_pace_sec_per_km + adjustment_seconds

    # Build recommendation based on altitude severity
    if altitude_feet < 5000:
        rec = "Minor adjustment needed. Focus on perceived effort rather than pace."
    elif altitude_feet < 7000:
        rec = "Moderate altitude effect. Use RPE/HR for E/L/T/I workouts. R-pace OK but increase recovery."
    else:
        rec = "Significant altitude effect. Strongly recommend effort-based (RPE/HR) pacing for all workouts except R-pace."

    return PaceAdjustment(
        base_pace_sec_per_km=base_pace_sec_per_km,
        adjusted_pace_sec_per_km=adjusted_pace,
        adjustment_seconds=adjustment_seconds,
        condition_type=ConditionType.ALTITUDE,
        severity=altitude_feet,
        reason=f"Altitude ({altitude_feet:,.0f}ft): ~{slowdown_pct * 100:.1f}% slower pacing",
        recommendation=rec,
    )


def adjust_pace_for_heat(
    base_pace_sec_per_km: int, temperature_celsius: float, humidity_pct: float = 50.0
) -> PaceAdjustment:
    """Adjust pace for heat and humidity.

    Heat significantly impairs performance. General guidelines:
    - 15-20°C (59-68°F): Optimal
    - 20-25°C (68-77°F): Slight slowdown (~2-3%)
    - 25-30°C (77-86°F): Moderate slowdown (~5-8%)
    - >30°C (>86°F): Significant slowdown (~10-15%)

    Humidity amplifies heat effects.

    Args:
        base_pace_sec_per_km: Normal pace in seconds per km
        temperature_celsius: Temperature in Celsius
        humidity_pct: Relative humidity percentage (0-100)

    Returns:
        PaceAdjustment with recommendation
    """
    # Optimal range: 15-20°C
    if temperature_celsius <= 20:
        return PaceAdjustment(
            base_pace_sec_per_km=base_pace_sec_per_km,
            adjusted_pace_sec_per_km=base_pace_sec_per_km,
            adjustment_seconds=0,
            condition_type=ConditionType.HEAT,
            severity=temperature_celsius,
            reason=f"Temperature ({temperature_celsius:.1f}°C) in optimal range",
            recommendation="No pace adjustment needed",
        )

    # Calculate base slowdown from temperature
    if 20 < temperature_celsius <= 25:
        base_slowdown_pct = 2.5  # 2-3% range
    elif 25 < temperature_celsius <= 30:
        base_slowdown_pct = 6.5  # 5-8% range
    elif 30 < temperature_celsius <= 35:
        base_slowdown_pct = 12.5  # 10-15% range
    else:  # >35°C
        base_slowdown_pct = 18.0  # 15-20% range

    # Adjust for humidity (adds ~0.5% per 10% humidity above 50%)
    humidity_factor = 0.0
    if humidity_pct > 50:
        humidity_factor = (humidity_pct - 50) / 10.0 * 0.5

    total_slowdown_pct = (base_slowdown_pct + humidity_factor) / 100.0

    adjustment_seconds = int(base_pace_sec_per_km * total_slowdown_pct)
    adjusted_pace = base_pace_sec_per_km + adjustment_seconds

    # Build recommendation
    if temperature_celsius <= 25:
        rec = "Slight pace adjustment. Stay hydrated and monitor effort."
    elif temperature_celsius <= 30:
        rec = "Moderate pace adjustment. Prioritize hydration. Consider moving workout to cooler time of day."
    else:
        rec = "Significant heat stress. Strongly consider treadmill or moving workout to early morning/evening. Shorten workout if needed."

    return PaceAdjustment(
        base_pace_sec_per_km=base_pace_sec_per_km,
        adjusted_pace_sec_per_km=adjusted_pace,
        adjustment_seconds=adjustment_seconds,
        condition_type=ConditionType.HEAT,
        severity=temperature_celsius,
        reason=f"Heat ({temperature_celsius:.1f}°C, {humidity_pct:.0f}% humidity): ~{total_slowdown_pct * 100:.1f}% slower",
        recommendation=rec,
    )


def adjust_pace_for_hills(base_pace_sec_per_km: int, grade_pct: float) -> PaceAdjustment:
    """Adjust pace for hills.

    On hills, effort is more important than pace. This function provides
    guidance but recommends effort-based pacing.

    Rough guidelines:
    - 1-3% grade: ~2-5 seconds/km slower
    - 3-5% grade: ~5-10 seconds/km slower
    - >5% grade: Strongly recommend effort-based pacing

    Args:
        base_pace_sec_per_km: Flat pace in seconds per km
        grade_pct: Hill grade percentage (positive for uphill)

    Returns:
        PaceAdjustment with recommendation
    """
    if abs(grade_pct) < 1.0:
        return PaceAdjustment(
            base_pace_sec_per_km=base_pace_sec_per_km,
            adjusted_pace_sec_per_km=base_pace_sec_per_km,
            adjustment_seconds=0,
            condition_type=ConditionType.HILLS,
            severity=grade_pct,
            reason=f"Grade ({grade_pct:.1f}%) negligible",
            recommendation="No pace adjustment needed",
        )

    # Calculate adjustment (simplified model)
    # ~3-4 seconds/km per 1% grade
    adjustment_seconds = int(abs(grade_pct) * 3.5)
    adjusted_pace = base_pace_sec_per_km + adjustment_seconds

    # Build recommendation
    if abs(grade_pct) < 3:
        rec = "Minor grade. Slight pace adjustment or use effort-based pacing (RPE/HR)."
    elif abs(grade_pct) < 5:
        rec = "Moderate grade. Strongly recommend effort-based pacing (RPE/HR) rather than pace target."
    else:
        rec = "Steep grade. Use effort-based pacing only (RPE/HR). Pace target not meaningful."

    return PaceAdjustment(
        base_pace_sec_per_km=base_pace_sec_per_km,
        adjusted_pace_sec_per_km=adjusted_pace,
        adjustment_seconds=adjustment_seconds,
        condition_type=ConditionType.HILLS,
        severity=grade_pct,
        reason=f"Grade ({grade_pct:.1f}%): ~{adjustment_seconds}s/km adjustment",
        recommendation=rec,
    )


def adjust_pace_for_conditions(
    base_pace_sec_per_km: int, condition_type: ConditionType, severity: float
) -> PaceAdjustment:
    """Unified function to adjust pace for any environmental condition.

    Args:
        base_pace_sec_per_km: Normal pace in seconds per km
        condition_type: Type of condition (altitude, heat, humidity, hills)
        severity: Severity value (altitude in ft, temp in °C, humidity in %, grade in %)

    Returns:
        PaceAdjustment with specific recommendations

    Raises:
        ValueError: If condition_type is invalid
    """
    if condition_type == ConditionType.ALTITUDE:
        return adjust_pace_for_altitude(base_pace_sec_per_km, severity)
    elif condition_type == ConditionType.HEAT:
        return adjust_pace_for_heat(base_pace_sec_per_km, severity)
    elif condition_type == ConditionType.HUMIDITY:
        # Humidity alone - treat as heat with high humidity
        return adjust_pace_for_heat(base_pace_sec_per_km, 25.0, severity)
    elif condition_type == ConditionType.HILLS:
        return adjust_pace_for_hills(base_pace_sec_per_km, severity)
    else:
        raise ValueError(f"Unsupported condition type: {condition_type}")

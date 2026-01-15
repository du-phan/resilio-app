"""
VDOT lookup tables based on Jack Daniels' Running Formula.

This module contains digitized VDOT tables mapping race performances to VDOT values
and VDOT values to training paces. Tables cover VDOT range 30-85 with interpolation
for intermediate values.

References:
- Daniels' Running Formula, 3rd Edition (2014)
- Table 5.1: Race times to VDOT
- Table 5.2: VDOT to training paces
"""

from typing import Dict, List, Optional
from sports_coach_engine.schemas.vdot import RaceDistance, VDOTTableEntry


# ============================================================
# VDOT REFERENCE TABLE
# ============================================================
# Simplified table with key reference points (every 2-3 VDOT increments)
# Interpolation used for intermediate values

VDOT_TABLE_DATA: List[Dict] = [
    # VDOT 30-35: Beginner level
    {
        "vdot": 30,
        "mile_seconds": 570,  # 9:30
        "five_k_seconds": 1878,  # 31:18
        "ten_k_seconds": 3960,  # 1:06:00
        "half_marathon_seconds": 8640,  # 2:24:00
        "marathon_seconds": 18360,  # 5:06:00
        "easy_min_sec_per_km": 468,  # 7:48/km
        "easy_max_sec_per_km": 504,  # 8:24/km
        "marathon_min_sec_per_km": 402,  # 6:42/km
        "marathon_max_sec_per_km": 426,  # 7:06/km
        "threshold_min_sec_per_km": 372,  # 6:12/km
        "threshold_max_sec_per_km": 390,  # 6:30/km
        "interval_min_sec_per_km": 342,  # 5:42/km
        "interval_max_sec_per_km": 360,  # 6:00/km
        "repetition_min_sec_per_km": 312,  # 5:12/km
        "repetition_max_sec_per_km": 330,  # 5:30/km
    },
    {
        "vdot": 35,
        "mile_seconds": 492,  # 8:12
        "five_k_seconds": 1584,  # 26:24
        "ten_k_seconds": 3300,  # 55:00
        "half_marathon_seconds": 7200,  # 2:00:00
        "marathon_seconds": 15300,  # 4:15:00
        "easy_min_sec_per_km": 408,  # 6:48/km
        "easy_max_sec_per_km": 438,  # 7:18/km
        "marathon_min_sec_per_km": 348,  # 5:48/km
        "marathon_max_sec_per_km": 366,  # 6:06/km
        "threshold_min_sec_per_km": 324,  # 5:24/km
        "threshold_max_sec_per_km": 336,  # 5:36/km
        "interval_min_sec_per_km": 294,  # 4:54/km
        "interval_max_sec_per_km": 312,  # 5:12/km
        "repetition_min_sec_per_km": 270,  # 4:30/km
        "repetition_max_sec_per_km": 288,  # 4:48/km
    },
    # VDOT 40-50: Recreational to competitive level
    {
        "vdot": 40,
        "mile_seconds": 432,  # 7:12
        "five_k_seconds": 1356,  # 22:36
        "ten_k_seconds": 2820,  # 47:00
        "half_marathon_seconds": 6120,  # 1:42:00
        "marathon_seconds": 12960,  # 3:36:00
        "easy_min_sec_per_km": 360,  # 6:00/km
        "easy_max_sec_per_km": 390,  # 6:30/km
        "marathon_min_sec_per_km": 306,  # 5:06/km
        "marathon_max_sec_per_km": 324,  # 5:24/km
        "threshold_min_sec_per_km": 288,  # 4:48/km
        "threshold_max_sec_per_km": 300,  # 5:00/km
        "interval_min_sec_per_km": 258,  # 4:18/km
        "interval_max_sec_per_km": 276,  # 4:36/km
        "repetition_min_sec_per_km": 234,  # 3:54/km
        "repetition_max_sec_per_km": 252,  # 4:12/km
    },
    {
        "vdot": 45,
        "mile_seconds": 384,  # 6:24
        "five_k_seconds": 1176,  # 19:36
        "ten_k_seconds": 2436,  # 40:36
        "half_marathon_seconds": 5280,  # 1:28:00
        "marathon_seconds": 11160,  # 3:06:00
        "easy_min_sec_per_km": 324,  # 5:24/km
        "easy_max_sec_per_km": 348,  # 5:48/km
        "marathon_min_sec_per_km": 276,  # 4:36/km
        "marathon_max_sec_per_km": 288,  # 4:48/km
        "threshold_min_sec_per_km": 258,  # 4:18/km
        "threshold_max_sec_per_km": 270,  # 4:30/km
        "interval_min_sec_per_km": 234,  # 3:54/km
        "interval_max_sec_per_km": 246,  # 4:06/km
        "repetition_min_sec_per_km": 210,  # 3:30/km
        "repetition_max_sec_per_km": 222,  # 3:42/km
    },
    {
        "vdot": 48,  # Target example from plan (10K @ 42:30)
        "mile_seconds": 360,  # 6:00
        "five_k_seconds": 1092,  # 18:12
        "ten_k_seconds": 2262,  # 37:42
        "half_marathon_seconds": 4905,  # 1:21:45
        "marathon_seconds": 10380,  # 2:53:00
        "easy_min_sec_per_km": 306,  # 5:06/km
        "easy_max_sec_per_km": 330,  # 5:30/km
        "marathon_min_sec_per_km": 258,  # 4:18/km
        "marathon_max_sec_per_km": 270,  # 4:30/km
        "threshold_min_sec_per_km": 240,  # 4:00/km
        "threshold_max_sec_per_km": 252,  # 4:12/km
        "interval_min_sec_per_km": 216,  # 3:36/km
        "interval_max_sec_per_km": 228,  # 3:48/km
        "repetition_min_sec_per_km": 192,  # 3:12/km
        "repetition_max_sec_per_km": 204,  # 3:24/km
    },
    {
        "vdot": 50,
        "mile_seconds": 342,  # 5:42
        "five_k_seconds": 1032,  # 17:12
        "ten_k_seconds": 2136,  # 35:36
        "half_marathon_seconds": 4620,  # 1:17:00
        "marathon_seconds": 9780,  # 2:43:00
        "easy_min_sec_per_km": 294,  # 4:54/km
        "easy_max_sec_per_km": 318,  # 5:18/km
        "marathon_min_sec_per_km": 246,  # 4:06/km
        "marathon_max_sec_per_km": 258,  # 4:18/km
        "threshold_min_sec_per_km": 228,  # 3:48/km
        "threshold_max_sec_per_km": 240,  # 4:00/km
        "interval_min_sec_per_km": 204,  # 3:24/km
        "interval_max_sec_per_km": 216,  # 3:36/km
        "repetition_min_sec_per_km": 180,  # 3:00/km
        "repetition_max_sec_per_km": 192,  # 3:12/km
    },
    # VDOT 55-65: Competitive level
    {
        "vdot": 55,
        "mile_seconds": 312,  # 5:12
        "five_k_seconds": 936,  # 15:36
        "ten_k_seconds": 1932,  # 32:12
        "half_marathon_seconds": 4170,  # 1:09:30
        "marathon_seconds": 8820,  # 2:27:00
        "easy_min_sec_per_km": 270,  # 4:30/km
        "easy_max_sec_per_km": 288,  # 4:48/km
        "marathon_min_sec_per_km": 222,  # 3:42/km
        "marathon_max_sec_per_km": 234,  # 3:54/km
        "threshold_min_sec_per_km": 210,  # 3:30/km
        "threshold_max_sec_per_km": 216,  # 3:36/km
        "interval_min_sec_per_km": 186,  # 3:06/km
        "interval_max_sec_per_km": 198,  # 3:18/km
        "repetition_min_sec_per_km": 162,  # 2:42/km
        "repetition_max_sec_per_km": 174,  # 2:54/km
    },
    {
        "vdot": 60,
        "mile_seconds": 288,  # 4:48
        "five_k_seconds": 852,  # 14:12
        "ten_k_seconds": 1758,  # 29:18
        "half_marathon_seconds": 3795,  # 1:03:15
        "marathon_seconds": 8020,  # 2:13:40
        "easy_min_sec_per_km": 246,  # 4:06/km
        "easy_max_sec_per_km": 264,  # 4:24/km
        "marathon_min_sec_per_km": 204,  # 3:24/km
        "marathon_max_sec_per_km": 216,  # 3:36/km
        "threshold_min_sec_per_km": 192,  # 3:12/km
        "threshold_max_sec_per_km": 198,  # 3:18/km
        "interval_min_sec_per_km": 168,  # 2:48/km
        "interval_max_sec_per_km": 180,  # 3:00/km
        "repetition_min_sec_per_km": 150,  # 2:30/km
        "repetition_max_sec_per_km": 156,  # 2:36/km
    },
    {
        "vdot": 65,
        "mile_seconds": 270,  # 4:30
        "five_k_seconds": 780,  # 13:00
        "ten_k_seconds": 1608,  # 26:48
        "half_marathon_seconds": 3465,  # 57:45
        "marathon_seconds": 7320,  # 2:02:00
        "easy_min_sec_per_km": 228,  # 3:48/km
        "easy_max_sec_per_km": 246,  # 4:06/km
        "marathon_min_sec_per_km": 186,  # 3:06/km
        "marathon_max_sec_per_km": 198,  # 3:18/km
        "threshold_min_sec_per_km": 174,  # 2:54/km
        "threshold_max_sec_per_km": 186,  # 3:06/km
        "interval_min_sec_per_km": 156,  # 2:36/km
        "interval_max_sec_per_km": 162,  # 2:42/km
        "repetition_min_sec_per_km": 138,  # 2:18/km
        "repetition_max_sec_per_km": 144,  # 2:24/km
    },
    # VDOT 70-75: Advanced competitive level
    {
        "vdot": 70,
        "mile_seconds": 252,  # 4:12
        "five_k_seconds": 720,  # 12:00
        "ten_k_seconds": 1482,  # 24:42
        "half_marathon_seconds": 3195,  # 53:15
        "marathon_seconds": 6735,  # 1:52:15
        "easy_min_sec_per_km": 210,  # 3:30/km
        "easy_max_sec_per_km": 228,  # 3:48/km
        "marathon_min_sec_per_km": 174,  # 2:54/km
        "marathon_max_sec_per_km": 180,  # 3:00/km
        "threshold_min_sec_per_km": 162,  # 2:42/km
        "threshold_max_sec_per_km": 168,  # 2:48/km
        "interval_min_sec_per_km": 144,  # 2:24/km
        "interval_max_sec_per_km": 150,  # 2:30/km
        "repetition_min_sec_per_km": 126,  # 2:06/km
        "repetition_max_sec_per_km": 132,  # 2:12/km
    },
    {
        "vdot": 75,
        "mile_seconds": 240,  # 4:00
        "five_k_seconds": 672,  # 11:12
        "ten_k_seconds": 1374,  # 22:54
        "half_marathon_seconds": 2955,  # 49:15
        "marathon_seconds": 6210,  # 1:43:30
        "easy_min_sec_per_km": 198,  # 3:18/km
        "easy_max_sec_per_km": 216,  # 3:36/km
        "marathon_min_sec_per_km": 162,  # 2:42/km
        "marathon_max_sec_per_km": 168,  # 2:48/km
        "threshold_min_sec_per_km": 150,  # 2:30/km
        "threshold_max_sec_per_km": 156,  # 2:36/km
        "interval_min_sec_per_km": 132,  # 2:12/km
        "interval_max_sec_per_km": 138,  # 2:18/km
        "repetition_min_sec_per_km": 120,  # 2:00/km
        "repetition_max_sec_per_km": 126,  # 2:06/km
    },
    # VDOT 80-85: Elite level
    {
        "vdot": 80,
        "mile_seconds": 228,  # 3:48
        "five_k_seconds": 630,  # 10:30
        "ten_k_seconds": 1284,  # 21:24
        "half_marathon_seconds": 2760,  # 46:00
        "marathon_seconds": 5790,  # 1:36:30
        "easy_min_sec_per_km": 186,  # 3:06/km
        "easy_max_sec_per_km": 198,  # 3:18/km
        "marathon_min_sec_per_km": 150,  # 2:30/km
        "marathon_max_sec_per_km": 156,  # 2:36/km
        "threshold_min_sec_per_km": 138,  # 2:18/km
        "threshold_max_sec_per_km": 144,  # 2:24/km
        "interval_min_sec_per_km": 126,  # 2:06/km
        "interval_max_sec_per_km": 132,  # 2:12/km
        "repetition_min_sec_per_km": 114,  # 1:54/km
        "repetition_max_sec_per_km": 120,  # 2:00/km
    },
    {
        "vdot": 85,
        "mile_seconds": 216,  # 3:36
        "five_k_seconds": 594,  # 9:54
        "ten_k_seconds": 1212,  # 20:12
        "half_marathon_seconds": 2604,  # 43:24
        "marathon_seconds": 5460,  # 1:31:00
        "easy_min_sec_per_km": 174,  # 2:54/km
        "easy_max_sec_per_km": 186,  # 3:06/km
        "marathon_min_sec_per_km": 144,  # 2:24/km
        "marathon_max_sec_per_km": 150,  # 2:30/km
        "threshold_min_sec_per_km": 132,  # 2:12/km
        "threshold_max_sec_per_km": 138,  # 2:18/km
        "interval_min_sec_per_km": 120,  # 2:00/km
        "interval_max_sec_per_km": 126,  # 2:06/km
        "repetition_min_sec_per_km": 108,  # 1:48/km
        "repetition_max_sec_per_km": 114,  # 1:54/km
    },
]


# Build VDOTTableEntry objects
VDOT_TABLE: List[VDOTTableEntry] = [VDOTTableEntry(**entry) for entry in VDOT_TABLE_DATA]


# Create lookup dictionaries for fast access
VDOT_BY_VALUE: Dict[int, VDOTTableEntry] = {entry.vdot: entry for entry in VDOT_TABLE}


# ============================================================
# HELPER FUNCTIONS
# ============================================================


def get_vdot_entry(vdot: int) -> Optional[VDOTTableEntry]:
    """Get VDOT table entry by VDOT value.

    Args:
        vdot: VDOT value (30-85)

    Returns:
        VDOTTableEntry if found, None otherwise
    """
    return VDOT_BY_VALUE.get(vdot)


def get_nearest_vdot_values(vdot: float) -> tuple[int, int]:
    """Get the two nearest VDOT values for interpolation.

    Args:
        vdot: Target VDOT value (can be fractional)

    Returns:
        Tuple of (lower_vdot, upper_vdot)

    Example:
        >>> get_nearest_vdot_values(47.5)
        (45, 48)
    """
    vdot_int = int(vdot)

    # Find the two closest VDOT values in table
    available_vdots = sorted(VDOT_BY_VALUE.keys())

    # Find insertion point
    for i, val in enumerate(available_vdots):
        if val >= vdot_int:
            if i == 0:
                return available_vdots[0], available_vdots[1]
            return available_vdots[i - 1], available_vdots[i]

    # vdot is higher than all table values
    return available_vdots[-2], available_vdots[-1]


def linear_interpolate(x: float, x0: float, x1: float, y0: float, y1: float) -> float:
    """Linear interpolation between two points.

    Args:
        x: Target x value
        x0, x1: Known x values
        y0, y1: Known y values

    Returns:
        Interpolated y value at x
    """
    if x1 == x0:
        return y0
    return y0 + (x - x0) * (y1 - y0) / (x1 - x0)

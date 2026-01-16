#!/usr/bin/env python3
"""
Automated training plan generation script.

This script orchestrates CLI commands to generate a complete training plan JSON
from athlete profile + goal. Implements the training-plan-design workflow programmatically.

Usage:
    python generate_plan.py --goal-type half_marathon --weeks 16 --output /tmp/plan.json

Dependencies:
    - sce CLI must be available
    - Athlete profile and goal must be set
    - Valid authentication for metrics access
"""

import subprocess
import json
import sys
import argparse
from datetime import date, timedelta
from typing import Dict, List, Any, Optional


def run_sce_command(cmd: List[str]) -> Dict[str, Any]:
    """
    Run sce CLI command and return parsed JSON result.

    Args:
        cmd: Command list (e.g., ['sce', 'status'])

    Returns:
        Parsed JSON response

    Raises:
        SystemExit: If command fails
    """
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error running command: {' '.join(cmd)}", file=sys.stderr)
        print(f"Exit code: {result.returncode}", file=sys.stderr)
        print(f"Output: {result.stdout}", file=sys.stderr)
        print(f"Error: {result.stderr}", file=sys.stderr)
        sys.exit(result.returncode)

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON from command: {' '.join(cmd)}", file=sys.stderr)
        print(f"Output: {result.stdout}", file=sys.stderr)
        sys.exit(1)


def gather_context() -> Dict[str, Any]:
    """
    Step 1: Gather athlete context (profile, status, goal).

    Returns:
        Dictionary with profile, metrics, and goal data
    """
    print("Step 1: Gathering athlete context...")

    # Get profile
    profile_result = run_sce_command(['sce', 'profile', 'get'])
    profile = profile_result['data']

    # Get current metrics
    status_result = run_sce_command(['sce', 'status'])
    metrics = status_result['data']

    context = {
        'profile': profile,
        'metrics': metrics,
        'ctl': metrics['ctl']['value'],
        'goal': profile['goal'],
    }

    print(f"  ✓ CTL: {context['ctl']}")
    print(f"  ✓ Goal: {context['goal']['type']} on {context['goal']['date']}")

    return context


def calculate_periodization(goal_type: str, weeks: int) -> Dict[str, Any]:
    """
    Step 2: Calculate phase allocation based on goal type and weeks available.

    Args:
        goal_type: Race distance (5k, 10k, half_marathon, marathon)
        weeks: Total weeks available

    Returns:
        Dictionary with phase allocation
    """
    print(f"\nStep 2: Calculating periodization for {weeks}-week {goal_type} plan...")

    # Phase percentages by goal type (simplified - see PERIODIZATION.md for full logic)
    phase_allocations = {
        '5k': {'base': 0.50, 'build': 0.38, 'peak': 0.12, 'taper': 0.12},
        '10k': {'base': 0.50, 'build': 0.38, 'peak': 0.12, 'taper': 0.12},
        'half_marathon': {'base': 0.47, 'build': 0.31, 'peak': 0.12, 'taper': 0.16},
        'marathon': {'base': 0.47, 'build': 0.31, 'peak': 0.12, 'taper': 0.16},
    }

    allocation = phase_allocations.get(goal_type, phase_allocations['half_marathon'])

    periodization = {
        'base_weeks': int(weeks * allocation['base']),
        'build_weeks': int(weeks * allocation['build']),
        'peak_weeks': int(weeks * allocation['peak']),
        'taper_weeks': max(2, int(weeks * allocation['taper'])),  # At least 2 weeks
    }

    # Place recovery weeks (every 4th week during base/build)
    recovery_weeks = []
    week_num = 4
    while week_num <= (periodization['base_weeks'] + periodization['build_weeks']):
        recovery_weeks.append(week_num)
        week_num += 4

    periodization['recovery_weeks'] = recovery_weeks

    print(f"  ✓ Base: {periodization['base_weeks']} weeks")
    print(f"  ✓ Build: {periodization['build_weeks']} weeks")
    print(f"  ✓ Peak: {periodization['peak_weeks']} weeks")
    print(f"  ✓ Taper: {periodization['taper_weeks']} weeks")
    print(f"  ✓ Recovery weeks: {recovery_weeks}")

    return periodization


def design_volume_progression(ctl: float, goal_type: str, periodization: Dict[str, Any]) -> List[float]:
    """
    Step 3: Design week-by-week volume progression.

    Args:
        ctl: Current CTL value
        goal_type: Race distance
        periodization: Phase allocation from calculate_periodization()

    Returns:
        List of weekly volumes (km)
    """
    print(f"\nStep 3: Designing volume progression from CTL {ctl}...")

    # Get safe starting volume and peak volume
    safe_volume_result = run_sce_command([
        'sce', 'guardrails', 'safe-volume',
        '--ctl', str(ctl),
        '--goal-type', goal_type
    ])

    start_volume = safe_volume_result['data']['recommended_start']
    peak_volume = safe_volume_result['data']['recommended_peak']

    print(f"  ✓ Starting volume: {start_volume} km/week")
    print(f"  ✓ Peak volume: {peak_volume} km/week")

    # Generate weekly volumes (simplified - real implementation would be more sophisticated)
    total_weeks = sum([
        periodization['base_weeks'],
        periodization['build_weeks'],
        periodization['peak_weeks'],
        periodization['taper_weeks']
    ])

    volumes = []
    current_volume = start_volume

    # Base phase: +10% per week (with recovery weeks)
    for week in range(1, periodization['base_weeks'] + 1):
        if week in periodization['recovery_weeks']:
            volumes.append(current_volume * 0.7)  # Recovery: 70%
        else:
            volumes.append(current_volume)
            if week not in periodization['recovery_weeks']:
                current_volume *= 1.10  # +10% increase

    # Build phase: +5% per week (slower progression)
    for week in range(periodization['build_weeks']):
        week_num = periodization['base_weeks'] + week + 1
        if week_num in periodization['recovery_weeks']:
            volumes.append(current_volume * 0.7)
        else:
            volumes.append(current_volume)
            current_volume *= 1.05

    # Peak phase: hold volume
    for _ in range(periodization['peak_weeks']):
        volumes.append(min(current_volume, peak_volume))

    # Taper phase: reduce 30% per week
    taper_start = peak_volume
    for i in range(periodization['taper_weeks']):
        reduction_factor = 0.70 ** (i + 1)  # Week 1: 70%, Week 2: 49%, etc.
        volumes.append(taper_start * reduction_factor)

    print(f"  ✓ Generated {len(volumes)} weeks of volume progression")

    return volumes


def calculate_vdot_paces(context: Dict[str, Any]) -> Dict[str, str]:
    """
    Step 4: Calculate training paces from VDOT.

    Args:
        context: Athlete context from gather_context()

    Returns:
        Dictionary of pace zones (E/M/T/I/R)
    """
    print("\nStep 4: Calculating training paces...")

    # Check if VDOT is in profile
    vdot = context['profile'].get('vdot')

    if not vdot:
        print("  ⚠ No VDOT in profile - using conservative default (48)")
        vdot = 48

    # Get training paces
    paces_result = run_sce_command(['sce', 'vdot', 'paces', '--vdot', str(vdot)])
    paces = paces_result['data']['paces']

    print(f"  ✓ E-pace: {paces['easy']}")
    print(f"  ✓ M-pace: {paces['marathon']}")
    print(f"  ✓ T-pace: {paces['threshold']}")
    print(f"  ✓ I-pace: {paces['interval']}")

    return paces


def generate_plan_json(
    context: Dict[str, Any],
    periodization: Dict[str, Any],
    volumes: List[float],
    paces: Dict[str, str],
    output_file: str
) -> None:
    """
    Steps 5-7: Generate full plan JSON with workouts and validation.

    Args:
        context: Athlete context
        periodization: Phase allocation
        volumes: Weekly volumes
        paces: Training pace zones
        output_file: Output file path
    """
    print("\nSteps 5-7: Generating plan JSON...")

    # TODO: Full implementation would:
    # - Generate week-by-week workout prescriptions (Step 5)
    # - Integrate multi-sport constraints (Step 6)
    # - Validate against guardrails (Step 7)

    # For now, create a skeleton JSON structure
    weeks = []
    start_date = date.today() + timedelta(days=7)  # Start next week

    for week_num, volume in enumerate(volumes, start=1):
        # Determine phase
        if week_num <= periodization['base_weeks']:
            phase = 'base'
        elif week_num <= periodization['base_weeks'] + periodization['build_weeks']:
            phase = 'build'
        elif week_num <= periodization['base_weeks'] + periodization['build_weeks'] + periodization['peak_weeks']:
            phase = 'peak'
        else:
            phase = 'taper'

        week_start = start_date + timedelta(weeks=week_num-1)
        week_end = week_start + timedelta(days=6)

        is_recovery = week_num in periodization['recovery_weeks']

        # Simplified workout structure (real implementation would be much more detailed)
        workouts = [
            {
                'id': f'w{week_num}_tue_easy',
                'week_number': week_num,
                'day_of_week': 1,  # Tuesday
                'date': (week_start + timedelta(days=1)).isoformat(),
                'workout_type': 'easy',
                'phase': phase,
                'duration_minutes': 30,
                'distance_km': round(volume * 0.15, 1),  # ~15% of weekly volume
                'intensity_zone': 'z2',
                'target_rpe': 3,
                'target_pace_per_km': paces['easy'],
                'purpose': 'Aerobic base',
                'surface': 'road',
            },
            # TODO: Add more workouts (quality sessions, long run, etc.)
        ]

        week_data = {
            'week_number': week_num,
            'phase': phase,
            'start_date': week_start.isoformat(),
            'end_date': week_end.isoformat(),
            'target_volume_km': round(volume, 1),
            'target_systemic_load_au': round(volume * 7, 1),  # Rough estimate
            'is_recovery_week': is_recovery,
            'notes': f'{"Recovery week" if is_recovery else phase.capitalize()} - Week {week_num}',
            'workouts': workouts
        }

        weeks.append(week_data)

    plan = {'weeks': weeks}

    # Save to file
    with open(output_file, 'w') as f:
        json.dump(plan, f, indent=2)

    print(f"  ✓ Plan JSON written to: {output_file}")
    print(f"  ✓ Total weeks: {len(weeks)}")
    print(f"  ✓ Total workouts: {sum(len(w['workouts']) for w in weeks)}")
    print("\n⚠ NOTE: This is a skeleton implementation.")
    print("  Real plan generation requires full workout prescription logic.")
    print("  See SKILL.md Step 5 for complete workout design guidance.")


def main():
    parser = argparse.ArgumentParser(description='Generate training plan JSON')
    parser.add_argument('--goal-type', required=True,
                       choices=['5k', '10k', 'half_marathon', 'marathon'],
                       help='Race distance')
    parser.add_argument('--weeks', type=int, required=True,
                       help='Total weeks for plan')
    parser.add_argument('--output', required=True,
                       help='Output file path (e.g., /tmp/plan.json)')

    args = parser.parse_args()

    print("=" * 60)
    print("Training Plan Generation")
    print("=" * 60)

    try:
        # Step 1: Gather context
        context = gather_context()

        # Step 2: Calculate periodization
        periodization = calculate_periodization(args.goal_type, args.weeks)

        # Step 3: Design volume progression
        volumes = design_volume_progression(context['ctl'], args.goal_type, periodization)

        # Step 4: Calculate VDOT paces
        paces = calculate_vdot_paces(context)

        # Steps 5-7: Generate plan JSON
        generate_plan_json(context, periodization, volumes, paces, args.output)

        print("\n" + "=" * 60)
        print("✓ Plan generation complete!")
        print("=" * 60)
        print(f"\nNext step: Review plan and populate via CLI:")
        print(f"  sce plan populate --from-json {args.output}")

    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

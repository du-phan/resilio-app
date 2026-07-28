"""
Core Modules - Internal domain logic.

These modules are NOT imported directly by Claude Code. They are called
by the API layer to implement coaching functionality.

Modules (M1-M13):
    - Workflows: Multi-step operation orchestration
    - M2 config: Configuration and secrets
    - M3 repository: File I/O operations
    - M4 profile: Athlete profile service
    - Activity sync: External import and reconciliation
    - Canonical activity schemas: Normalized local archive
    - M7 notes: Notes and RPE analysis
    - M8 load: Load calculation
    - M9 metrics: CTL/ATL/TSB computation
    - M10 plan: Plan generation
    - M11 adaptation: Workout adaptation
    - M12 enrichment: Data context enrichment
    - M13 memory: Insights extraction
"""

# Note: These are NOT re-exported at package level
# Only RepositoryIO is exposed for direct file access

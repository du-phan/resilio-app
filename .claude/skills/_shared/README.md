# Shared Agent Skills Resources

This directory contains resources shared across multiple agent skills in the coaching system.

## Directory Purpose

The `_shared/` directory serves as a central location for resources that are:
1. **Truly generic** - Apply to all or most skills without modification
2. **Reusable** - Used by 3+ skills with identical content
3. **Foundational** - Core conventions, standards, or utilities

## When to Use Shared vs Skill-Specific Resources

### ✅ Use Shared Resources For:
- **Cross-skill conventions**: Naming standards, file structure patterns
- **Common utilities**: Scripts, helpers used by multiple skills
- **Generic templates**: If a template is identical across 3+ skills
- **Architectural documentation**: Skill system design, best practices

### ❌ Keep Resources Skill-Specific For:
- **Domain knowledge**: Training methodology, specific to one skill's workflow
- **Workflow templates**: Even if similar structure, if content differs by skill
- **Reference files**: CLI commands, decision trees, edge cases specific to one skill
- **Examples**: Skill-specific scenarios and demonstrations

## Current Architecture (2026-01-19)

**All templates are skill-specific** - This is intentional and correct:
- `monthly-transition/templates/monthly_review.md` - Monthly transition assessment
- `injury-risk-management/templates/risk_analysis.md` - Injury risk reports
- `plan-adaptation/templates/adaptation_plan.md` - Plan replanning scenarios
- `race-preparation/templates/race_week_*.md` - Distance-specific race schedules
- `training-plan-design/templates/plan_presentation.md` - Initial plan review

**Reference files are skill-specific extracts** - Each skill contains focused references:
- `cli_reference.md` - Commands relevant to that skill's workflow
- `decision_trees.md` - Decision logic for that skill's scenarios
- `edge_cases.md` - Unusual situations for that skill's domain

## Design Principle: Self-Contained Skills

**Priority**: Self-contained skills > Shared dependencies

**Benefits**:
1. **Independence**: Skills can be understood, modified, or removed without affecting others
2. **Context efficiency**: LLM agents load only relevant context for the active skill
3. **Maintainability**: Changes to one skill don't ripple to others
4. **Clarity**: All resources for a skill are in one place

**When self-containment conflicts with DRY** (Don't Repeat Yourself):
- For skills: **Favor self-containment** (some duplication is acceptable)
- For core system code: **Favor DRY** (extract to shared utilities)

## Directory Structure

```
.claude/skills/
├── _shared/               # Shared resources (this directory)
│   ├── README.md          # This file
│   └── docs/              # Architectural documentation
│       └── conventions.md # Shared conventions and standards
├── daily-workout/         # Individual skill directories
│   ├── SKILL.md          # Skill definition
│   ├── references/       # Skill-specific references
│   ├── templates/        # Skill-specific templates (if any)
│   └── examples/         # Skill-specific examples
├── training-plan-design/
│   ├── SKILL.md
│   ├── references/
│   ├── templates/
│   └── examples/
└── ...
```

## Naming Conventions

**Files**: `lowercase_with_underscores.md`
- ✅ `cli_reference.md`, `decision_trees.md`, `monthly_review.md`
- ❌ `CLI_REFERENCE.md`, `DecisionTrees.md`, `monthlyReview.md`

**Directories**: `lowercase-with-hyphens/`
- ✅ `injury-risk-management/`, `race-preparation/`
- ❌ `InjuryRiskManagement/`, `race_preparation/`

**Reason**: Unix conventions, case-sensitivity safety, LLM-friendly consistency

## Progressive Disclosure Pattern

All skills follow **progressive disclosure**:
1. **SKILL.md**: Workflow steps and high-level guidance (<500 lines)
2. **references/**: Detailed methodology, loaded on-demand
3. **templates/**: Output formats for reports and presentations
4. **examples/**: Complete scenarios demonstrating skill usage

**Goal**: SKILL.md should be scannable and actionable without being overwhelming. Details are one reference away.

## Best Practices

### For Skill Developers

1. **Start skill-specific**: When creating a new skill, put all resources in the skill directory
2. **Extract after 3x duplication**: Only move to `_shared/` after seeing identical content in 3+ skills
3. **Document extraction**: Add header comments explaining where shared resources come from
4. **Test independence**: Ensure skill works if `_shared/` is empty (graceful degradation)

### For Maintainers

1. **Audit shared resources**: Review `_shared/` quarterly to ensure everything is still used
2. **Deprecate carefully**: If removing shared resources, update all skills that reference them
3. **Preserve skill history**: Use `git mv` when moving files to preserve commit history

## Future Enhancements

Potential candidates for shared resources (not yet needed):
- **Shared templates**: If multiple skills need identical report formats
- **Common utilities**: Shell functions used across skills (e.g., date calculations)
- **Test fixtures**: If skills share test data or validation logic

## Questions?

See:
- `docs/coaching/methodology.md` - Training methodology and coaching principles
- [CLI Command Index](../../docs/coaching/cli/index.md) - Complete CLI command documentation
- Individual skill SKILL.md files - Skill-specific workflows and guidance

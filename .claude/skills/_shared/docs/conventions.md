# Agent Skills Conventions & Standards

Documentation of naming conventions, file structure patterns, and best practices for agent skills in the coaching system.

---

## File Naming Conventions

### Markdown Files

**Format**: `lowercase_with_underscores.md`

**Examples**:
- ✅ `cli_reference.md`
- ✅ `decision_trees.md`
- ✅ `monthly_review.md`
- ✅ `pace_zones.md`
- ✅ `acwr_zones.md`

**Avoid**:
- ❌ `CLI_REFERENCE.md` (all uppercase)
- ❌ `DecisionTrees.md` (CamelCase)
- ❌ `monthlyReview.md` (camelCase)

**Rationale**:
1. **Unix convention**: Lowercase is standard on Unix/Linux systems
2. **Case-sensitivity safety**: Prevents issues on case-sensitive filesystems
3. **LLM-friendly**: Single pattern reduces cognitive load for AI agents
4. **Consistency**: One rule to remember, not multiple variations

---

## Directory Naming Conventions

### Skill Directories

**Format**: `lowercase-with-hyphens/`

**Examples**:
- ✅ `daily-workout/`
- ✅ `injury-risk-management/`
- ✅ `race-preparation/`
- ✅ `training-plan-design/`

**Avoid**:
- ❌ `DailyWorkout/` (CamelCase)
- ❌ `injury_risk_management/` (underscores)

### Subdirectories

**Standard structure**:
```
skill-name/
├── SKILL.md              # Skill definition (UPPERCASE exception for visibility)
├── references/           # Reference documentation
├── templates/            # Output templates
└── examples/             # Usage examples
```

**Required**:
- `SKILL.md` - Every skill must have this file

**Optional** (create only if needed):
- `references/` - For progressive disclosure of detailed content
- `templates/` - For structured output formats
- `examples/` - For complete scenario demonstrations

---

## SKILL.md Structure

### File Size Limit

**Maximum**: 500 lines

**Rationale**: Claude Code best practice for agent skills. Longer files should extract details to reference files.

**If exceeding 500 lines**:
1. Identify sections with implementation details
2. Extract to reference files (e.g., `references/detailed_workflow.md`)
3. Keep workflow steps in SKILL.md, reference details via links

### Required Sections

```markdown
---
name: skill-name
description: Brief description with "when to use" triggers
allowed-tools: Bash, Read, Write, AskUserQuestion
context: fork
agent: general-purpose
---

# Skill Name

## Overview
[2-3 paragraphs: what, why, when]

## Workflow
### Step 0: [First step]
### Step 1: [Second step]
...

## Decision Trees
[Key decision points with options]

## Common Pitfalls
[Frequent mistakes and how to avoid]
```

### Description Format

**Must include**:
1. **What**: What the skill does
2. **When**: Specific triggers for activation

**Examples**:
```yaml
# Good
description: Provide daily workout recommendations with adaptation logic. Use when athlete asks "what should I do today?", "today's workout", or "should I train today?".

# Better
description: Design personalized training plans for 5K-Marathon races using Pfitzinger periodization. Use when athlete requests "design my plan", "create training program", or after first-session onboarding.

# Avoid (missing triggers)
description: Helps design training plans for races.
```

---

## Reference Files

### Purpose

Reference files contain **detailed content** loaded on-demand via links from SKILL.md.

### Common Reference Files

**CLI commands**:
- `cli_reference.md` - Skill-specific command extracts

**Methodology**:
- `pace_zones.md`, `periodization.md`, `volume_progression.md`

**Decision support**:
- `decision_trees.md` - Structured decision logic
- `edge_cases.md` - Unusual situations and handling

**Guardrails**:
- `guardrails.md` - Safety limits and validation rules

### Header Format for Skill-Specific Extracts

If a reference file is a skill-specific extract (not comprehensive), add header:

```markdown
# Title

> **Note**: This is a **skill-specific extract** containing only [topic] relevant to [skill] workflows. For comprehensive documentation, see `docs/[topic]/[file].md`.

[Content...]
```

**Example**:
```markdown
# CLI Command Reference

> **Note**: This is a **skill-specific extract** containing only commands relevant to injury risk management workflows. For comprehensive CLI documentation, see [CLI Command Index](../../../docs/coaching/cli/index.md).

Quick reference for injury risk management commands.
```

---

## Template Files

### Purpose

Templates provide **structured formats** for skill outputs (reports, plans, reviews).

### Location

`templates/` subdirectory within each skill:
```
skill-name/
└── templates/
    ├── template_name.md
    └── another_template.md
```

### Format

Use **placeholder syntax** with clear labels:

```markdown
# Report Title [Placeholder]

## Section Name
- **Field**: [value]
- **Another Field**: [value]

[Descriptive guidance for filling this section]
```

**Example**:
```markdown
# Month [N] Training Plan Review

## Assessment Summary (Month [N-1])
- **Adherence**: [X]%
- **CTL Progression**: [status]
- **VDOT**: [value] [if recalibrated]

[Coach observations and guidance]
```

---

## Progressive Disclosure Pattern

### Principle

**SKILL.md should be scannable** - high-level workflow with links to details.

### Three-Tier Structure

1. **Tier 1 - SKILL.md** (workflow steps, <500 lines)
   - What to do in each step
   - Links to reference files for details

2. **Tier 2 - references/** (methodology details, load on-demand)
   - How to execute steps
   - Deep dives into techniques

3. **Tier 3 - Training books** (comprehensive resources)
   - Complete methodology from authoritative sources
   - Linked from reference files for deep exploration

### Example

**In SKILL.md** (Step 3):
```markdown
### Step 3: Calculate Periodization

Divide weeks into phases (base, build, peak, taper).

**See [PERIODIZATION.md](references/periodization.md) for**:
- Standard allocation percentages
- Distance-specific adjustments
- Phase calculation examples
```

**In references/periodization.md**:
```markdown
## Phase Allocation Calculation

### Standard Allocation Percentages
- Base: 45-50% of total weeks
- Build: 30-35% of total weeks
...

[Detailed formulas, examples, edge cases]

For complete periodization theory, see:
- [Advanced Marathoning](../../../docs/training_books/advanced_marathoning.md)
```

---

## Skill-Specific vs Shared Resources

### Keep Skill-Specific When:

- **Content differs by skill** - Even if structure is similar
- **Domain knowledge** - Training methodology specific to one workflow
- **Self-contained benefit** - Skill can be understood independently
- **Fewer than 3 uses** - Not worth extracting to shared until 3+ skills need it

### Extract to Shared When:

- **Identical content** across 3+ skills
- **Generic utilities** - Scripts, helpers with no skill-specific logic
- **Cross-skill conventions** - Standards that apply to all skills

### Current Status (2026-01-19)

✅ **All reference files are correctly skill-specific**:
- `cli_reference.md` (3 skills) - Each contains different command subsets
- `decision_trees.md` (3 skills) - Each contains skill-specific decision logic
- `edge_cases.md` (3 skills) - Each contains skill-specific unusual situations

✅ **All templates are correctly skill-specific**:
- Each template is unique to its skill's output format

✅ **No shared resources needed yet** - Skills are properly self-contained

---

## Git Workflow

### File Renaming

**Always use `git mv`** to preserve history:

```bash
# Good
git mv OLD_NAME.md new_name.md

# Avoid (loses history)
mv OLD_NAME.md new_name.md
git add new_name.md
git rm OLD_NAME.md
```

### Commit Messages

**Format**: `<type>(<scope>): <description>`

**Examples**:
```
refactor(skills): standardize reference file naming to lowercase
feat(monthly-transition): add monthly review template
docs(shared): document skill conventions and architecture
```

---

## Validation Checklist

Use this checklist before committing skill changes:

### File Naming
- [ ] All `.md` files use `lowercase_with_underscores.md`
- [ ] All directories use `lowercase-with-hyphens/`
- [ ] Exception: `SKILL.md` is uppercase for visibility

### SKILL.md Structure
- [ ] File is <500 lines (extract details if over)
- [ ] Description includes "when to use" triggers
- [ ] Workflow has clear Step N structure
- [ ] Links to reference files use correct lowercase names

### Reference Files
- [ ] Skill-specific extracts have header noting relationship to full docs
- [ ] Files are focused on one topic
- [ ] Cross-references between files use correct paths

### Templates
- [ ] Use clear placeholder syntax ([value], [X], [N])
- [ ] Include guidance comments for each section
- [ ] Located in `templates/` subdirectory

### Testing
- [ ] All markdown links work (no 404s)
- [ ] Skill can be activated and references load correctly
- [ ] No broken references to renamed files

---

## Future Enhancements

### Potential Additions (Not Yet Needed)

1. **Linting automation**: Script to validate naming conventions
2. **Link checker**: Verify all markdown links resolve correctly
3. **Size checker**: Alert when SKILL.md approaches 500 lines
4. **Template validator**: Ensure templates have required sections

---

## Questions?

See:
- [../README.md](../README.md) - Shared resources architecture
- [docs/coaching/methodology.md](../../../docs/coaching/methodology.md) - Training methodology
- Individual skill SKILL.md files - Skill-specific workflows

# Complete-Setup Skill Evaluations

This directory contains evaluation scenarios for testing the complete-setup skill's effectiveness, accuracy, and adherence to best practices.

## Purpose

Evaluation scenarios validate that the skill:
1. **Functions correctly** across different platforms and edge cases
2. **Maintains conversational tone** appropriate for non-technical users
3. **Demonstrates adaptive workflow** by skipping completed steps
4. **Handles errors gracefully** with clear explanations and recovery paths
5. **Provides educational value** by explaining concepts, not just running commands

## Evaluation Files

### fresh_macos_m1.json
**Scenario**: First-time setup on macOS with Apple Silicon
- Tests complete workflow from scratch (no Python, no package, no config)
- Validates Homebrew installation flow
- Tests Poetry-based package installation
- Verifies conversational tone and non-technical explanations
- Expected duration: Full workflow (all 5 phases)

### ubuntu_upgrade_python.json
**Scenario**: Ubuntu 22.04 with Python 3.10 (needs upgrade)
- Tests Python upgrade workflow via deadsnakes PPA
- Validates venv-based package installation
- Tests sudo explanation for non-technical users
- Verifies virtual environment teaching and activation retention
- Handles Ubuntu-specific issues (externally-managed-environment, build tools)
- Expected duration: Full workflow with Python upgrade

### partial_setup_recovery.json
**Scenario**: Resume interrupted setup (Python present, package missing)
- Tests adaptive workflow intelligence (skip completed phases)
- Validates Phase 1 detection accuracy
- Verifies efficient recovery (no redundant work)
- Tests decision tree logic (exit code handling)
- Expected duration: Phases 1, 3, 4 only (skip Phase 2)

## How to Use Evaluations

### Manual Testing

1. **Prepare environment** matching the scenario (e.g., fresh macOS VM, Ubuntu 22.04 container)
2. **Activate skill** with the query from the JSON file
3. **Observe behavior** against `expected_behavior` list
4. **Validate quality criteria** (conversational tone, error handling, etc.)
5. **Check for anti-patterns** (avoid technical jargon, external docs, etc.)

### Automated Testing (Future)

No automated evaluation runner is defined in this repo yet. Use manual testing for now.

## Evaluation Criteria

Each scenario tests multiple dimensions:

### Functional Correctness
- Commands execute successfully
- Exit codes interpreted correctly
- Environment validated properly
- Handoff to first-session works

### User Experience
- Conversational, non-technical tone
- Clear explanations of technical concepts
- Visual confirmations (prompt indicators, output patterns)
- No context switch to external documentation

### Adaptive Intelligence
- Detects existing installations
- Skips completed phases
- Resumes interrupted setups efficiently
- No redundant work

### Error Handling
- Recovers gracefully from common errors
- Provides clear diagnostic information
- Explains what went wrong and how to fix it
- Maintains conversation flow during recovery

### Educational Value
- Explains WHY each step is needed, not just WHAT
- Uses analogies for complex concepts
- Teaches best practices (venv activation, PATH management)
- Empowers user to troubleshoot independently

## Success Metrics

A successful evaluation should demonstrate:
- ✓ All `expected_behavior` items occur in order
- ✓ All `quality_criteria` are met
- ✓ None of the `anti_patterns_to_avoid` occur
- ✓ Common errors are handled gracefully (if applicable)
- ✓ User ends with working environment and understands next steps

## Adding New Evaluations

To create a new evaluation scenario:

1. **Identify the use case**: What specific scenario are you testing?
2. **Define expected behavior**: Step-by-step list of what should happen
3. **Specify quality criteria**: What makes this scenario successful?
4. **List anti-patterns**: What mistakes should be avoided?
5. **Document edge cases**: What unusual conditions might occur?

**Template**:
```json
{
  "skills": ["complete-setup"],
  "query": "User's initial request",
  "files": [],
  "expected_behavior": [
    "Step 1: Detection...",
    "Step 2: Installation...",
    "Step 3: Validation..."
  ],
  "quality_criteria": {
    "criterion_1": "What this means",
    "criterion_2": "Another quality check"
  },
  "anti_patterns_to_avoid": [
    "Don't do this",
    "Avoid that"
  ]
}
```

## Platform Coverage

Current evaluations cover:
- ✓ macOS (Apple Silicon, Homebrew, Poetry)
- ✓ Linux (Ubuntu/Debian, APT, venv)
- ✓ Adaptive workflow (partial setup recovery)

**Gaps** (future evaluations):
- CentOS/RHEL (YUM package manager)
- macOS Intel (different Homebrew paths)
- Mixed state recovery (both Poetry and venv exist)
- Network failures during installation
- Multiple Python versions causing conflicts

## Continuous Improvement

As the skill evolves:
- Add evaluations for new features
- Update existing scenarios to reflect best practices
- Expand platform coverage
- Document common failure patterns
- Refine quality criteria based on user feedback

---

**Note**: These evaluations align with Anthropic's agent skill best practices (particularly "Build evaluations first" - line 710 of best practices guide).

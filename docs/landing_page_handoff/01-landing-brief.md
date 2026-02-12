# Landing Brief (Core)

## Purpose

Define the minimum product and conversion requirements for the official landing page implementation in a separate website repository.

## User Moment

Athletes are trying to improve running while juggling other sports, work, travel, and recovery. Most plans break when real life changes.
The page should trigger an immediate recognition response: "yes, this is exactly my issue."

## Product Promise

Sports Coach Engine is a conversation-first AI coach for hybrid training. It uses a CLI toolkit under the hood, so coaching feels natural while decisions stay grounded in measurable training data.

Truth boundary (v0):
The generated plan is running-first, but it is coordinated around other sports using total training load and recovery tradeoffs.

## Core Problem

Rigid, run-only plans ignore total training load and force athletes into false tradeoffs: follow the plan and burn out, or skip sessions and lose progress.

## Category Definition

Hybrid training here means:
running plus an evolving mix of other sports (for example bouldering, pilates, HIIT, surfing, strength),
often without a single multi-discipline event as the organizing goal.

## Problem Truths (From User Quotes)

1. Athletes struggle to coordinate running with variable combinations of other sports and life constraints.
2. Existing running apps often cannot ingest or plan around non-running sessions, forcing manual workarounds.
3. Recovery interference is the practical pain: hard run sessions can block strength/climbing sessions and vice versa.
4. Priorities shift by week or season; static weekly templates create guilt and plan-break cascades.
5. Many athletes optimize for sustainable progress and enjoyment, not maximal run-only performance.
6. Athletes want adaptation with rationale: what changed, why it changed, and what tradeoff is being managed.
7. Many athletes prefer fewer runs per week (2-3) plus other cardio, as long as progress is still meaningful.

Primary evidence source:
`docs/long_term_vision/[Run app] User quotes.csv`

## Moat

1. AI reasoning plus quantitative toolkit, not a rigid rule engine.
2. Multi-sport load model (systemic + lower-body) for real adaptation.
3. Explainable tradeoffs and transparent coaching rationale.
4. Local-first workflow with explicit Strava boundaries.
5. Built for hybrid training across everyday sport mixes (for example running + bouldering/pilates/HIIT/surfing), not triathlon-style event planning.

## Primary Outcome

Visitor starts a coaching session by using the starter prompt.

## Non-Goals

1. Do not ship final brand UI in this repo.
2. Do not prescribe final visual art direction to the external design team.
3. Do not claim unsupported integrations or outcomes.
4. Do not segment the landing narrative by technical proficiency.

## Non-Negotiables

1. Positioning remains adaptive coaching for athletes with full training lives.
2. Primary CTA intent remains immediate start with AI coach.
3. Starter prompt remains available and copyable.
4. Setup and privacy facts remain explicit and truthful.

## Required Facts

1. Supported setup workflow: macOS, Linux.
2. Unsupported setup workflow: Windows, WSL.
3. Strava account plus one-time app credentials are required.
4. First sync may pause on Strava API limits and resume later.
5. Project data is local-first with Strava used for auth and sync.

## Source-of-Truth References

1. `docs/long_term_vision/[Run app] Product Vision Doc.md`
2. `docs/mvp/v0_product_requirements_document.md`
3. `docs/mvp/v0_technical_specification.md`
4. `docs/coaching/methodology.md`
5. `AGENTS.md`
6. `CLAUDE.md`

## Deliverable Scope

This core brief governs both:

1. the reference prototype (`docs/getting_started.html`)
2. the external website implementation contract.

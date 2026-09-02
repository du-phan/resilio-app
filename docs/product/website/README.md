# Public product contract

This document is the public-claim boundary for Resilio v0.3.0. Runtime
references and schemas remain authoritative when this summary is incomplete.

## Positioning

Resilio is a local AI-assisted running coach for multi-sport athletes. It
prescribes running while treating climbing, cycling, skiing, strength work,
surfing, and other non-running sports as athlete-managed context.

Resilio does not produce a multi-sport workout plan, add unlike load
quantities, calculate a composite readiness score, or estimate injury
probability. It separates synchronized facts, missing evidence, coaching
judgment, and proposed actions.

## Evidence and approval

Intervals.icu is the sole external boundary for completed activities, native
analysis, wellness and training-state evidence, sport settings, and planned
running-workout calendar readback. Provider-derived values retain their
provider labels, dates, coverage, and native units.

The coach proposes changes with rationale. An athlete approval binds the exact
plan content before Resilio applies or publishes it. Missing provider evidence
is explicit and is never silently reconstructed or treated as neutral.

## Methodology

Race plans can select Daniels, marathon-specific Pfitzinger, or Fitzgerald
80/20 as a conceptual methodology. FIRST remains unavailable until its
edition-specific source tables are verified. VDOT is race-performance
equivalence evidence; it is not an automatic training-pace table.

When race evidence is missing, disputed, conflicting, or stale, Resilio can
propose a separate baseline-assessment plan before race planning.

## Data boundaries

Canonical athlete state, plans, approvals, and coaching evidence are persisted
locally. Resilio reads evidence from and can publish approved running workouts
to Intervals.icu. The selected Claude Code or Codex environment processes the
coaching context supplied to it. Optional weather lookup sends location
coordinates to Open-Meteo.

Intervals.icu may forward an eligible workout to Garmin. Forwarding
eligibility is not proof that the workout reached a watch.

## Supported setup

The guided setup workflow is supported on macOS. An Intervals.icu account and
personal API key are required. Linux and Windows are not advertised until
their onboarding paths are implemented and verified.

## Website release rule

Public website copy, examples, metadata, and downloads must name a released
tag and agree with this contract. The v0.3.0 website may state that Resilio no
longer uses the Strava API, but historical policy claims must cite Strava's
current primary documentation and include a review date.

The synthetic example in this directory is public test data. It contains no
athlete record and must stay labelled as illustrative.

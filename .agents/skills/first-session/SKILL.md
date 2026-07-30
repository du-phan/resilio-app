---
name: first-session
description: Onboard a new athlete through Intervals.icu authentication, coordinated activity and wellness sync, athlete-confirmed profile creation, goal capture, VDOT approval, methodology-explicit macro planning, and the first approved weekly plan. Use for first-time setup or a new athlete profile.
---

# First session

Keep the conversation in athlete language. Do not expose commands, tools, skill
names, or local paths. Use one Poetry environment throughout.

## Authority and safety

- Treat synchronized completed activities, wellness, and sport settings as the
  factual provider record.
- Treat profile fields, constraints, goals, and approved VDOT as
  athlete-confirmed facts.
- Present provider thresholds, heart rates, power, pace, and VO2 max only as
  candidates. Never copy them into the profile without explicit confirmation.
- Never derive a missing value, convert provider VO2 max into VDOT, or present a
  composite readiness or injury-risk score.
- Ask about pain, illness, pregnancy, medication, or medical restrictions when
  relevant. Do not diagnose; recommend appropriate professional care for
  medical red flags.

## Workflow

1. Verify the CLI and account with:

   ```bash
   poetry run resilio auth status
   ```

   If the credential is absent, ask the athlete to obtain their personal
   Intervals.icu API key. Store only `INTERVALS_ICU_API_KEY=<key>` in
   `.env.local` with mode `0600`. Never print or inspect the secret.

2. Run the coordinated import:

   ```bash
   poetry run resilio sync
   poetry run resilio sync --status
   ```

   Report the returned window, counts, partial state, quarantines, and
   completion matches exactly. Do not claim that quarantined or ambiguous rows
   were imported.

3. Establish dates and inspect factual state:

   ```bash
   poetry run resilio dates today
   poetry run resilio status
   poetry run resilio profile get
   poetry run resilio profile candidates
   poetry run resilio memory list --type INJURY_HISTORY
   ```

4. Create or update the profile from confirmed facts. Collect:

   - athlete name, age, and running experience;
   - minimum and maximum run days, unavailable days, and maximum session
     duration in minutes;
   - running priority, other-sport commitments, and conflict policy;
   - the IANA timezone used for training schedules;
   - usual training location for local weather planning.

   Ask this in athlete language: “Where do you usually train?”
   Persist the confirmed answer through the profile `--weather-location`
   option.

   Use synchronized history to avoid asking questions that the data already
   answers, but do not store computed recent volume, typical workout patterns,
   provider vital signs, or provider thresholds in the profile.

5. Review each provider candidate with its unit, sport scope, observation date,
   provider record identity, and temporary flag. Ask for confirmation before
   updating any athlete-owned fact. Missing candidates remain missing.

6. Record confirmed personal bests with exact elapsed time and performance
   date. Capture the goal type, target date, and optional target finish time.
   Discuss feasibility from current evidence and the available plan horizon.

7. Complete the approval chain in order:

   - run the baseline VDOT proposal procedure and retain its exact JSON file;
   - after explicit approval, bind that exact file with
     `resilio approvals approve-vdot --file <PROPOSAL_JSON>`;
   - compute the first plan Monday with `resilio dates`, then create the
     immutable evidence gate with `resilio plan create-macro-context
     --evidence-as-of <DATE> --start <MONDAY>`;
   - run the macro-plan procedure and present its methodology rationale;
   - after explicit approval, record `resilio approvals approve-macro`;
   - generate the first exact weekly proposal file;
   - after explicit approval, bind it with
     `resilio approvals approve-week --file <WEEK_JSON>`;
   - apply that unchanged file and verify persistence.

   The VDOT approval history, active plan, immutable macro context, macro
   approval, weekly approval, applied-week audit, and closed-cycle references
   are one coordinated planning aggregate. Never repair or replace an approved
   file or content-addressed evidence artifact in place.

## Completion

Finish only when authentication works, coordinated sync state is accurately
reported, the profile contains only confirmed durable facts, constraints and
other sports are complete, the goal is recorded, and the VDOT, macro plan, and
first week have each passed their separate approval boundary.

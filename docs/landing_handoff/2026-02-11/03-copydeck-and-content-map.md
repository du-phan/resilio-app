# Copydeck and Content Map (Core)

## Section Map (Required)
1. `#hero`
2. `#who-its-for`
3. `#why-different`
4. `#start-now`
5. `#how-it-works`
6. `#privacy`

Note: `#who-its-for` anchor is retained for contract stability, but the visible section can frame the problem and user moment instead of audience labels.

## Hero
### Eyebrow (recommended)
Sports Coach Engine

### Headline
Hybrid training, finally supported.

### Support line
If you lift, climb, pilates, HIIT, surf, cycle, and run, many plans still live in silos. Start in chat: Sports Coach Engine coordinates your training week, adapts as life shifts, and explains every adjustment and tradeoff.

### Primary CTA
Start with the AI coach now

## Problem section (`#who-its-for`)
Optional opener line above the bullets:
- "I'm not training for a triathlon. I just need a plan that respects the rest of my week."

- "I wish I could tell my running app about my other workouts and have it plan around them."
- "Hard run days wreck my legs for everything else."
- "One missed run breaks the whole plan."

## Why different
- Conversation-first coach with immediate guided start.
- AI reasoning + quantitative toolkit instead of rigid templates.
- Multi-sport load awareness with explainable adaptations.
- Explicitly built for hybrid training life, not triathlon-plan framing.

## Start now
### Steps
1. Open Claude Code or Codex.
2. Open this project folder.
3. Paste the starter prompt.

### Starter prompt
Help me get started. I train across multiple sports. Guide me step by step.

## How it works
1. Guided setup and Strava auth.
2. Sync and baseline context.
3. Profile, goal, and adaptive planning.

## Quick reality check (must appear)
This is not a standalone section; it should be a compact callout embedded near `#start-now`.

- Supported: macOS, Linux.
- Not supported in the current setup workflow: Windows, WSL.
- Requires a Strava account + API app credentials (Client ID/Secret, one-time).
- First sync may hit Strava API rate limits; higher-volume histories may require 15-minute resume windows.

## Privacy
Project data is local-first. Strava is used for authorization and activity sync.

## Content Constraints
1. Keep section intros short and scannable.
2. Keep one dominant conversion path.
3. Avoid duplicate high-emphasis CTA blocks.
4. Keep the narrative problem-first and inspiration-led.
5. Use concrete user-language pain statements, not abstract category copy.

## User-Voice Quotes (Internal Reference)
Primary quote to anchor problem recognition:
1. "I go to run club once a week and an intense cross training workout 3x a week and I wish I could tell [my running app] about them and have it incorporate and/or plan around those."
   - Source: `docs/long_term_vision/[Run app] User quotes.csv`
   - URL: `https://www.reddit.com/r/runna/comments/1k9qseq/how_do_you_manage_your_training_plan_if_you_also/`

Backup quotes:
1. "Wow this is my exact problem rn...trying to fit in running and climbing and lifting weights!!"
   - URL: `https://www.reddit.com/r/running/comments/c3ftdm/how_do_you_incorporate_other_sports_into_your/`
2. "I love to run but I don't want to do it so often that I stop loving it..."
   - URL: `https://www.reddit.com/r/runna/comments/1kr2zgp/struggling_to_combine_running_with_other_sports/`

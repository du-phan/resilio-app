# Design Patterns and Design Systems Research (Advisory)

## Advisory Scope

This document informs the website design team. It does not prescribe final visual direction.

Extraction date: 2026-02-11

## 1. Benchmark Method and Selection

Selection criteria:

1. Strong landing-page clarity for broad product audiences.
2. Clear CTA hierarchy and low-friction entry.
3. Reusable patterns for GitHub-oriented or developer-first products.
4. Evidence of minimalist, conversion-oriented structure.

Benchmarks reviewed:

1. OpenClaw: https://openclaw.ai
2. Supabase: https://supabase.com
3. PostHog: https://posthog.com
4. Vercel: https://vercel.com
5. Stripe: https://stripe.com

## 2. Benchmark Pattern Extraction

### OpenClaw

Observed pattern:

- Direct problem-solution hero and action-first framing.

What it solves:

- Fast comprehension for first-time visitors.

When to use:

- Product category requires immediate "what this does" clarity.

Avoid when:

- Proof and trust requirements are too weak to support short copy.

Evidence:

- "The AI that actually does things." and immediate capability framing (openclaw.ai, captured 2026-02-11).

### Supabase

Observed pattern:

- Concise hero plus trust row near the fold.

What it solves:

- Rapid trust transfer for infrastructure-like products.

When to use:

- Broad platform products needing quick credibility.

Avoid when:

- Brand has no validated trust assets.

Evidence:

- Hero + action + trust logos (supabase.com, captured 2026-02-11).

### PostHog

Observed pattern:

- Sharp positioning line and immediate get-started path.

What it solves:

- Conversion for visitors ready to evaluate now.

When to use:

- Product audience includes hands-on evaluators.

Avoid when:

- Onboarding prerequisites are hidden or ambiguous.

Evidence:

- Positioning-forward hero and direct action (posthog.com, captured 2026-02-11).

### Vercel

Observed pattern:

- Strong headline with nearby outcome evidence.

What it solves:

- Balances ambition with concrete proof.

When to use:

- Product has measurable benefits to reference.

Avoid when:

- Outcomes are not validated.

Evidence:

- Hero + measurable customer outcomes (vercel.com, captured 2026-02-11).

### Stripe

Observed pattern:

- Category-defining headline with clean progressive disclosure.

What it solves:

- Enterprise confidence without long preamble.

When to use:

- Infrastructure products with multiple entry points.

Avoid when:

- Messaging cannot be backed by operational depth.

Evidence:

- Clear leadership framing + immediate onboarding actions (stripe.com, captured 2026-02-11).

## 3. Design System Synthesis

### Primer (GitHub)

Reference: https://primer.style
Key takeaway:

- Accessible primitives and clear information hierarchy map well to GitHub-native products.

### Atlassian Foundations/Tokens

Reference: https://atlassian.design/foundations/ and https://atlassian.design/foundations/tokens/
Key takeaway:

- Tokens should be treated as source-of-truth design decisions.

### Material token hierarchy

Reference: https://material-web.dev/theming/material-theming/
Key takeaway:

- Reference/system/component token layers reduce implementation drift.

### USWDS tokens

Reference: https://designsystem.digital.gov/design-tokens/
Key takeaway:

- Tokenized values improve consistency and design-dev handoff quality.

## 4. Minimalist Conversion Principles

### UX heuristics and plain-language content

1. Use usability heuristics to reduce friction and confusion.
   - Source: https://www.nngroup.com/articles/ten-usability-heuristics/
2. Use plain-language structure optimized for scanning.
   - Source: https://www.gov.uk/guidance/content-design/writing-for-gov-uk

### Performance guardrails

Use Core Web Vitals thresholds for p75 of visits:

- LCP <= 2.5s
- INP <= 200ms
- CLS <= 0.1
  Source: https://web.dev/articles/vitals and https://web.dev/articles/optimize-lcp

## 5. Reusable Pattern Table (Advisory)

| Pattern                              | What it solves                   | When to use                              | Avoid when                                    | Evidence source              |
| ------------------------------------ | -------------------------------- | ---------------------------------------- | --------------------------------------------- | ---------------------------- |
| Minimal hero + one primary CTA       | Immediate orientation and action | New visitors with low context            | Product needs long legal preconditions at top | OpenClaw, PostHog            |
| Trust strip near fold                | Confidence without long prose    | You can show validated constraints/proof | Proof assets are weak or unverified           | Supabase, Vercel             |
| Guided-start module with copy action | Reduces first-step ambiguity     | Conversational onboarding products       | Action is not truly executable                | PostHog install flow pattern |
| Reality/constraints block            | Prevents expectation mismatch    | Prerequisite-heavy onboarding            | Requirements are trivial                      | Internal product docs        |
| Privacy boundary block               | Reduces data trust friction      | Any product touching account data        | Boundaries are unknown                        | Internal product docs        |
| Compact objections accordion         | Handles predictable friction     | Conversion pages with known objections   | Too many unresolved unknowns                  | GOV.UK + benchmark practice  |

## 6. Anti-Patterns to Avoid

1. Decorative layers that compete with CTA and readability.
2. Repeated high-emphasis cards with no hierarchy.
3. Duplicate CTA bands with no new decision value.
4. Long explanatory paragraphs before first action.
5. Unverified logos, testimonials, or results claims.

## 7. Advisory to Design Team

Design team authority includes:

1. final visual style and brand expression,
2. layout language and component aesthetics,
3. motion and interaction style,

as long as product truth, conversion intent, and factual constraints from the core contract are preserved.

## 8. Vision-to-Pattern Mapping (From Internal Product Docs)

Source alignment:

1. `docs/long_term_vision/[Run app] Product Vision Doc.md`
2. `docs/mvp/v0_product_requirements_document.md`
3. `docs/mvp/v0_technical_specification.md`
4. `docs/coaching/methodology.md`

Implications for final landing expression:

1. Lead with the problem: rigid plans vs real multi-sport life.
2. Show mechanism without implementation noise: "conversation-first AI coach" and "data-grounded adaptation".
3. Preserve trust early: support limits, Strava dependency, local-first boundary.
4. Keep final visuals minimal, modern, and high-signal, with one dominant conversion action.
5. Make the moat explicit: hybrid lifestyle training (running + other sports) and not triathlon-plan positioning.

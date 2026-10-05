# Running progression evaluation results

Two independent agent passes answered the eight synthetic scenarios without
receiving the rubric, earlier coaching answers, or one another's responses.
The primary implementation agent reviewed every response against
[rubric.md](rubric.md). This is a qualitative review of 16 responses, not a
statistical reliability estimate or an automated keyword test.

Raw outputs are preserved in [pass 1](responses-pass-1.json) and
[pass 2](responses-pass-2.json). No real athlete records or external payloads
were used in these fixtures or responses.

| Scenario | Pass 1 | Pass 2 | Observed behavior |
| --- | --- | --- | --- |
| Low-volume extension | Pass | Pass | Separates 27.4% session extension from 56.5% weekly share; qualifies nominal duration and coverage; reuses recovery answers. |
| Recovery-week comparator | Pass | Pass | Uses completed 15 km within 30 days for the 13.3% extension; keeps broader consistency uncertain. |
| Planned is not completed | Pass | Pass | Rejects missed 13/15 km as capacity evidence; proposes rebuilding and same-goal amendment without cramming. |
| Pain after undercompletion | Pass | Pass | Defers escalation and requests appropriate clinical reassessment without diagnosis. |
| Equal shares | Pass | Pass | Distinguishes absolute sessions, duration, frequency, and supporting volume; percentage alone does not settle readiness. |
| Holiday and HR | Pass | Pass | Scopes no climbing to Barcelona; preserves recovery intent and qualifies HR as effort evidence. |
| Immutable target mismatch | Pass | Pass | Routes unsupported total to a safer same-goal amendment rather than filler or silent edits. |
| Race goal and pace | Pass | Pass | Separates equivalence from endurance and prediction; invents neither success probability nor training pace. |

Both passes gave a recommendation and a usable fallback. Recommendations do
not constitute exact-workout approval. Reasonable alternative distances were
accepted when supported by the supplied facts and uncertainty.

The responses evaluate the shared coaching decision procedure installed during
implementation. They were collected before the final skill edits that moved
binding commands into the executable sequence and made the final proposal path
explicit; those edits preserve the decision guidance. Final authoring order,
exact candidate/evidence bindings, fresh source reproof, consent races,
conditional-week rejection, and state recovery are separately verified by the
deterministic lifecycle and CLI tests. These examples do not prove performance
for every athlete or instruction variation.

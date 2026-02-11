# Implementation Contract (Core)

## 1. Ownership Split
### Design team owns
1. Visual style and brand expression.
2. Component aesthetics and layout decisions.
3. Motion language and interaction polish.

### Product team owns
1. Truth claims and prohibited claims.
2. Conversion intent and primary path.
3. Setup/privacy factual constraints.
4. Starter prompt contract.

## 2. Fixed Requirements (Must Preserve)
1. Required section intents and anchors:
   - `#hero`, `#who-its-for`, `#why-different`, `#start-now`, `#how-it-works`, `#privacy`
2. Primary CTA intent: immediate start with AI coach.
3. Starter prompt text exactly:
   - Help me get started. I train across multiple sports. Guide me step by step.
4. Mandatory factual blocks:
   - support matrix
   - Strava requirement
   - rate-limit expectation
   - local-first privacy boundary
5. No prohibited claims from `02-messaging-and-claims.md`.
6. Differentiation language must preserve the hybrid-training moat and avoid triathlon-plan positioning.

## 3. Section Intent Clarification
1. `#who-its-for` anchor is contract-fixed, but visible title/copy can be problem-first (for example "The problem this fixes").
2. Landing narrative should focus on user problem, inspiration, and outcome.
3. Do not segment core landing copy by technical proficiency.
4. Include concrete recognition statements so visitors can self-identify quickly ("yes, that's my issue").

## 4. Adaptable Elements (Design Freedom)
1. Visual hierarchy and layout strategy.
2. Typography and spacing system.
3. Component implementation details.
4. Animation and micro-interactions.
5. Framework and frontend architecture in official repo.

## 5. Conversion Flow Contract
Primary flow:
1. Hero -> primary CTA -> start-now module -> copy prompt -> coach conversation.

Constraint visibility:
1. Visitors must be able to find the "Quick reality check" constraints near `#start-now` without leaving the page.

## 6. Accessibility and Performance Baseline
1. WCAG 2.2 AA baseline.
2. Core Web Vitals target (p75):
   - LCP <= 2.5s
   - INP <= 200ms
   - CLS <= 0.1

## 7. Out of Scope
1. New product feature claims.
2. Unsupported platform claims.
3. Social proof that cannot be verified.
4. Rewriting product truth for brand style preferences.

# Architecture debt: split `resilio/core/plan.py`

Baseline: 2,630 lines on 2026-07-28. This module exceeds the 1,500-line hard
limit and is temporarily allowlisted. Decompose generation, validation,
progression, matching, and persistence responsibilities in separate work.

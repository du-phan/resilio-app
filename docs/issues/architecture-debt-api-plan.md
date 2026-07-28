# Architecture debt: split `resilio/api/plan.py`

Baseline: 2,948 lines on 2026-07-28. This module exceeds the 1,500-line hard
limit and is temporarily allowlisted. The current migration may add only a
narrow publication seam; the file may not grow. Decompose by plan query,
approval, generation, and publication responsibilities in separate work.

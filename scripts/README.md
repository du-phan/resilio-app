# Development & Testing Scripts

This directory contains one-time utilities and manual testing scripts used during development. These files are excluded from version control (see `.gitignore`).

## Files

### OAuth & Token Management

**`get_strava_token.py`**
- **Purpose**: Exchange Strava authorization code for access tokens
- **Usage**: `python scripts/get_strava_token.py "AUTHORIZATION_CODE"`
- **Output**: Saves tokens to `config/secrets.local.yaml`
- **When to use**: First-time Strava OAuth setup or token regeneration

**`oauth_helper.py`**
- **Purpose**: Interactive OAuth flow helper (deprecated, use `get_strava_token.py` instead)
- **Status**: Not used in final implementation

### Data Sync & Testing

**`sync_strava.py`**
- **Purpose**: Standalone Strava activity sync utility
- **Usage**: `python scripts/sync_strava.py [--days 30]`
- **Features**:
  - Fetches activities from last N days (default 30)
  - Bypasses full pipeline for quick data inspection
  - Useful for debugging API responses
- **When to use**: Testing Strava API integration without running full pipeline

**`test_pipeline.py`**
- **Purpose**: End-to-end pipeline test with real Strava data
- **Usage**: `python scripts/test_pipeline.py`
- **Pipeline**: M5 (Strava) → M7 (Notes) → M6 (Normalize) → M8 (Load)
- **Output**: Displays RPE estimates and load calculations for recent activities
- **When to use**: Validating full Phase 2 pipeline integration

## Notes

- All scripts require valid Strava credentials in `config/secrets.local.yaml`
- These are development utilities, not production code
- See `tests/unit/` for automated test suites
- Data samples stored in `data_samples/` (also gitignored)

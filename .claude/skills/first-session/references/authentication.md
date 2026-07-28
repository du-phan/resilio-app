# Account validation reference

Resilio uses one personal Intervals.icu API key through HTTP Basic
authentication. The single-athlete application has no browser callback or
token-refresh lifecycle.

## Setup

1. Run `resilio init` if `.env.local` does not exist.
2. Ask the athlete for the API key from their Intervals.icu settings page.
3. Save `INTERVALS_ICU_API_KEY=<key>` in `.env.local`.
4. Set file mode `0600`.
5. Run `resilio auth status`.

Never display the key, an Authorization header, a credential-bearing URL, or
a raw response body.

## Outcomes

- Missing credential: collect/save the key, then retry.
- Authentication rejected: the key is invalid or revoked; ask for a new key.
- Authorization rejected: access is valid but the requested operation is not
  allowed; do not retry blindly.
- Rate limited: honor the reported retry interval and resume later.
- Network failure: retry only through the client’s bounded read policy.

## Operational notes

Garmin and Wahoo should connect to Intervals.icu so completed activities can be
imported and approximately the next seven days of planned workouts can be
forwarded. Their workout filters must include the relevant sport. Intervals,
phone, and device timezones must agree for Wahoo scheduling.

Free accounts should be opened at least once every 90 days to avoid dormancy
and paused file processing.

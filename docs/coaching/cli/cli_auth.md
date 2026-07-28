# Account validation

`resilio auth status` validates the personal Intervals.icu API key without
displaying it.

The only secret is `INTERVALS_ICU_API_KEY` in `.env.local`. The configuration
loader parses that file into a local mapping and never mutates the process
environment. Tests inject a fake mapping and never read the developer file.

```bash
resilio auth status
```

Outcomes distinguish missing configuration, rejected authentication, rejected
authorization, rate limiting, network failure, and invalid external payloads.
CLI envelopes never contain the key, Authorization headers, raw response
bodies, or credential-bearing URLs.

This single-athlete application uses personal-key Basic authentication and has
no browser callback, code exchange, or refresh-token command.

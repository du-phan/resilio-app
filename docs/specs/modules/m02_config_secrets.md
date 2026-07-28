# Runtime configuration and secrets

Non-secret settings live in `config/settings.yaml`. The sole production secret
is `INTERVALS_ICU_API_KEY` in `.env.local`.

`load_config(repo_root, environment=None)`:

1. validates strict non-secret settings;
2. uses an explicitly supplied mapping when present;
3. otherwise parses `.env.local` into a local mapping without mutating global
   environment state;
4. validates a non-empty key and stores it as Pydantic `SecretStr`.

Tests always pass fake mappings and are prohibited from reading the developer
file. Errors distinguish missing configuration, parse/validation failures,
authentication rejection, authorization rejection, rate limiting, and
network failure. String representations, logs, envelopes, and fixtures must
never reveal the key.

There is no YAML secret model, client ID/secret pair, access token, refresh
token, callback, or token expiry state.

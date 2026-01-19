# Authentication Commands

> **Quick Links**: [Back to Index](index.md) | [Core Concepts](core_concepts.md)

OAuth flow and token management for Strava integration.

**Commands in this category:**
- `sce auth url` - Get Strava OAuth authorization URL
- `sce auth exchange` - Exchange authorization code for access token
- `sce auth status` - Check current authentication status

---

## sce auth url

Get Strava OAuth authorization URL.

**Usage:**

```bash
sce auth url
```

**Returns:**

```json
{
  "ok": true,
  "data": {
    "url": "https://www.strava.com/oauth/authorize?...",
    "instructions": "Open this URL in your browser and authorize..."
  }
}
```

**Next steps:**

1. Open URL in browser
2. Authorize application
3. Copy authorization code from redirect URL
4. Run `sce auth exchange --code YOUR_CODE`

---

## sce auth exchange

Exchange authorization code for access token.

**Usage:**

```bash
sce auth exchange --code CODE
```

**Parameters:**
- `--code CODE` - Authorization code from OAuth redirect URL (required)

**Example:**

```bash
sce auth exchange --code 1234567890abcdef
```

**Returns:**

```json
{
  "ok": true,
  "data": {
    "status": "authenticated",
    "expires_at": "2026-02-14T10:30:00Z",
    "next_steps": "Run 'sce sync' to import activities"
  }
}
```

**Token Storage:**

- Saved to `config/secrets.local.yaml`
- Automatically refreshed when expired
- Never committed to git (in .gitignore)

---

## sce auth status

Check current authentication status.

**Usage:**

```bash
sce auth status
```

**Returns:**

```json
{
  "ok": true,
  "data": {
    "authenticated": true,
    "expires_at": "2026-02-14T10:30:00Z",
    "expires_in_hours": 720
  }
}
```

**Exit codes:**

- `0`: Token valid
- `3`: Token expired or missing - refresh required

**Common workflow:**

```bash
# Check if authentication is needed
sce auth status
if [ $? -eq 3 ]; then
  echo "Token expired - refreshing..."
  sce auth url
  # Follow OAuth flow...
fi
```

---

**Navigation**: [Back to Index](index.md) | [Next: Data Commands](cli_data.md)

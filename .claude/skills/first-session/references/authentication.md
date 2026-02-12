# Authentication Guide: OAuth Flow

## Overview

Historical activity data from Strava is essential for intelligent coaching. Without it, you're coaching blind with CTL=0 and no context about the athlete's training patterns.

---

## Why Authentication Matters

**With authentication** (6 months / 180 days of history):
- Ask: "I see you average 35km/week - should we maintain this?"
- Reference actual data: "Your CTL is 44 (solid recreational fitness)"
- Detect injuries: "I notice a 2-week gap in November with CTL drop"

**Without authentication**:
- Ask: "How much do you run?" (no context, generic)
- Start from CTL=0 (no baseline)
- No multi-sport visibility
- Miss historical injury patterns

---

## OAuth Flow

### Step 1: Check Authentication Status

```bash
resilio auth status
```

**Exit codes**:
- **0**: Authenticated (proceed to sync)
- **2**: Config missing (run `resilio init` first)
- **3**: Expired/missing (guide OAuth flow below)

### Step 2: Generate Authorization URL

```bash
resilio auth url
```

**Returns**: OAuth URL like `https://strava.com/oauth/authorize?client_id=...&redirect_uri=...`

### Step 3: Instruct Athlete

**Explain why**:
"I need access to your Strava data to provide intelligent coaching based on your actual training patterns, not guesses."

**Instructions**:
1. Open this URL in your browser
2. Click "Authorize" to grant access
3. Copy the code from the final page
4. Paste it here

### Step 4: Wait for Athlete to Provide Code

Athlete will be redirected to a page showing:
```
Authorization successful!
Your code: ABC123XYZ789
```

### Step 5: Exchange Code for Tokens

```bash
resilio auth exchange --code ABC123XYZ789
```

**Success**: Tokens stored, authentication complete

**Failure**: Common errors:
- Code expired (10 min timeout): Generate new URL, start over
- Invalid code: Check for typos, regenerate if needed
- Network error: Retry exchange command

### Step 6: Confirm Success

```bash
resilio auth status
# Exit code 0 = success
```

**Message to athlete**:
"Great! I can now access your training history. Let me sync your activities."

---

## Troubleshooting

### Q: Athlete doesn't have a Strava account

**Response**: Strava authentication is required for data-driven coaching. Guide the athlete to create a free account at strava.com and record a few activities before proceeding. Without Strava data, the system cannot calculate CTL, detect patterns, or provide personalized coaching.

### Q: Authorization code expired

**Scenario**: Athlete took too long (>10 minutes) to provide code.

**Response**:
```
The authorization code expired (they timeout after 10 minutes). Let me generate a new URL.

[Run: resilio auth url]

Here's a fresh authorization link. This time, I'll wait right here - just authorize and paste the code within a few minutes.
```

### Q: Athlete has no recent Strava data

**Scenario**: Sync returns 0 activities or very few (<10 in 6 months / 180 days).

**Response**:
```
I see you don't have much recent activity on Strava (or this is a new account). No problem - we'll start from scratch.

Your CTL will start at 0, which means we'll build your training volume gradually from a conservative baseline.
```

**Profile setup adjustments**:
- Ask directly: "How much have you been running weekly?" (no data to reference)
- Use stated volume to estimate starting CTL equivalent
- Ask about injury history directly (no activity gaps to reference)

### Q: Network error during exchange

**Scenario**: `resilio auth exchange` fails with network error.

**Response**:
```
Network error occurred while exchanging the authorization code. Let me try again.

[Retry: resilio auth exchange --code ABC123]

[If still fails:]
Check your network connection. The code is still valid for ~10 minutes, so we can retry when your network is stable.
```

### Q: Athlete authorized but sync fails

**Scenario**: `resilio auth status` returns 0, but `resilio sync` fails.

**Response**:
```
Your Strava account is connected, but sync failed. This can happen if:
1. Network issue (retry: resilio sync)
2. Strava API rate limit (wait 15 min, retry)
3. Account has no public activities (check Strava privacy settings)

Let's try syncing again.
```

---

## Complete Command Reference

| Command | Purpose | Exit Codes |
|---------|---------|------------|
| `resilio auth status` | Check authentication state | 0=ok, 2=no config, 3=expired |
| `resilio auth url` | Generate OAuth URL | 0=success |
| `resilio auth exchange --code CODE` | Exchange code for tokens | 0=success, 4=network, 5=invalid |
| `resilio auth refresh` | Refresh expired tokens (auto) | 0=success |
| `resilio auth revoke` | Remove stored tokens | 0=success |

---

## Security & Privacy Notes

**What access is granted**:
- Read activity data (distance, pace, HR, notes)
- Read profile info (name, age if public)
- NO write access (cannot create/modify activities)
- NO access to private notes unless made visible

**Token storage**:
- Tokens stored locally in `config/secrets.local.yaml` (`strava.access_token`, `strava.refresh_token`, `strava.token_expires_at`)
- Never logged or transmitted elsewhere
- Refresh tokens auto-renew without re-authorization

**Athlete can revoke anytime**:
- Strava account settings → "Apps, Services, and Devices" → Revoke access
- Or: `resilio auth revoke` command

---

## Additional Resources

- **OAuth 2.0 spec**: https://oauth.net/2/
- **Strava API docs**: https://developers.strava.com/docs/authentication/
- **CLI reference**: [Authentication Commands](../../../docs/coaching/cli/cli_auth.md)

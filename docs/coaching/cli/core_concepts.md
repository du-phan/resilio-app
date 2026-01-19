# CLI Core Concepts

> **Quick Links**: [Back to Index](index.md)

Fundamental concepts for working with Sports Coach Engine CLI commands.

## JSON Response Structure

All `sce` commands return JSON with this consistent structure:

```json
{
  "schema_version": "1.0",
  "ok": true,
  "error_type": null,
  "message": "Human-readable summary",
  "data": {
    /* command-specific payload with rich interpretations */
  }
}
```

### Field Definitions

- **schema_version**: Response format version (currently "1.0")
- **ok**: Boolean success indicator
  - `true`: Operation succeeded, parse `data`
  - `false`: Operation failed, check `error_type` and `message`
- **error_type**: Error category (see Exit Codes below)
- **message**: Human-readable description of result or error
- **data**: Command-specific payload
  - Contains rich interpretations (e.g., "CTL 44 = solid recreational fitness")
  - Includes zone classifications, trend indicators, recommendations

### Using Rich Interpretations

Don't just read raw values - use the interpretations:

```bash
# ❌ Bad: Generic coaching
"Your CTL is 44"

# ✅ Good: Use interpretations
result=$(sce status)
ctl=$(echo "$result" | jq -r '.data.ctl.value')
interpretation=$(echo "$result" | jq -r '.data.ctl.interpretation')
echo "Your CTL is $ctl ($interpretation)"
# Output: "Your CTL is 44 (solid recreational fitness level)"
```

---

## Exit Codes Reference

Always check exit codes after command execution:

```bash
sce status
exit_code=$?
```

### Exit Code Table

| Code  | Meaning                | Error Type                    | Action                              |
| ----- | ---------------------- | ----------------------------- | ----------------------------------- |
| **0** | Success                | -                             | Parse JSON and proceed              |
| **2** | Config/Setup Missing   | `config_missing`              | Run `sce init` to initialize        |
| **3** | Authentication Failure | `auth_error`                  | Run `sce auth url` to refresh token |
| **4** | Network/Rate Limit     | `network_error`, `rate_limit` | Retry with exponential backoff      |
| **5** | Invalid Input          | `validation_error`            | Check parameters and retry          |
| **1** | Internal Error         | `internal_error`              | Report issue with traceback         |

### Error Handling Pattern

```bash
sce sync
case $? in
  0)
    echo "Sync successful"
    ;;
  2)
    echo "Config missing - run: sce init"
    sce init
    ;;
  3)
    echo "Auth expired - refreshing token"
    sce auth url
    # Wait for user to authorize...
    ;;
  4)
    echo "Network issue - retrying in 30s"
    sleep 30
    sce sync
    ;;
  5)
    echo "Invalid parameters - check command syntax"
    sce sync --help
    ;;
  *)
    echo "Internal error - check logs"
    ;;
esac
```

### Error Type to Exit Code Mapping

- `config_missing` → Exit code 2
- `auth_error` → Exit code 3
- `network_error`, `rate_limit` → Exit code 4
- `validation_error`, `invalid_input`, `insufficient_data` → Exit code 5
- All other errors → Exit code 1

---

## Parsing CLI Output

### Using `jq`

```bash
# Extract specific field
result=$(sce status)
ctl=$(echo "$result" | jq -r '.data.ctl.value')
echo "CTL: $ctl"

# Check if command succeeded
ok=$(echo "$result" | jq -r '.ok')
if [ "$ok" = "true" ]; then
  echo "Success"
fi

# Extract error message
if [ "$ok" = "false" ]; then
  error=$(echo "$result" | jq -r '.message')
  echo "Error: $error"
fi
```

### Combined Error Handling

```bash
sce status
exit_code=$?

case $exit_code in
  0)
    echo "Success"
    ;;
  2)
    echo "Run 'sce init' first"
    ;;
  3)
    echo "Auth expired - run 'sce auth url'"
    ;;
  4)
    echo "Network/rate limit - retry later"
    ;;
  5)
    echo "Invalid input - check parameters"
    ;;
  *)
    echo "Internal error"
    ;;
esac
```

---

## See Also

- [Command Index](index.md) - Complete command reference
- [Coaching Scenarios](../scenarios.md) - Example workflows
- [Training Methodology](../methodology.md) - Understanding metrics

---

**Navigation**: [Back to Index](index.md)

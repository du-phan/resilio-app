# Activity commands

Canonical completed activities are read from
`data/activities/YYYY-MM/<local_activity_id>.yaml`.

```bash
resilio activity list --since 30d
resilio activity list --since 60d --sport run
resilio activity search --query "ankle fatigue" --since 90d
resilio activity export --since 28d --out /tmp/activities.json
resilio activity laps <local-activity-id>
```

`list` and `search` expose derived convenience values such as kilometres and
minutes, while persisted activity v2 stores SI base units. `laps` presents the
provider-neutral `segments` collection, which may come from historical laps or
external intervals.

There is no active local manual-entry command. Record manual climbing,
bouldering, yoga, strength, or other sessions in Intervals.icu and sync them.
Historical local manual records remain preserved as historical imports.

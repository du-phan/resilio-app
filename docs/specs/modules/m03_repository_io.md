# Repository I/O

`RepositoryIO` owns validated YAML/JSON access under the repository root.
Typed reads return the requested Pydantic model or a structured repository
error. Writes serialize aliases so canonical activity `_schema` appears
literally.

Provider transport is not a repository concern. Canonical activity files use:

```text
data/activities/YYYY-MM/<local_activity_id>.yaml
```

The activity archive repository validates every record as schema version 2,
checks unique local and external IDs, checks stable paths, and uses atomic
same-directory writes.

Migration and sync services add their own higher-level transaction boundaries:
hash-manifested backups, staging directories, atomic directory switches,
rollback directories, checkpoint artifacts, and exclusive locks. Profile,
metrics, plans, sync state, and publication state are included when a
coordinated backup is required.

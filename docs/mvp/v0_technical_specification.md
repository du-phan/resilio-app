# v0 technical specification — superseded history

The original numbered-module design has been superseded. Do not use this file
to infer current imports, state schemas, credentials, sync behavior, or
commands.

Current dependency direction is:

```text
configuration -> integration client/DTOs -> mappers -> canonical schemas
-> repositories/core services -> API -> CLI
```

The current system uses a canonical activity v2 archive, strict Intervals.icu
DTOs, checkpointed reconciliation, local metric computation, typed structured
workouts, and ownership-proven calendar publication.

See:

- [Architecture map](../reference/architecture-map.md)
- [API layer](../specs/api_layer.md)
- [Core workflow services](../specs/modules/m01_workflows.md)
- [Runtime configuration](../specs/modules/m02_config_secrets.md)
- [Canonical activity v2](../specs/modules/m06_activity_normalization.md)

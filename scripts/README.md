# Utility scripts

Application workflows belong in the `resilio` CLI. This directory is reserved
for narrowly scoped developer diagnostics and migration helpers that are not
part of the athlete-facing command surface.

Do not add standalone credential exchange, completed-activity sync, or
calendar mutation scripts. External transport belongs in
`resilio/integrations/intervals_icu`; archive and publication operations must
go through their validated core services.

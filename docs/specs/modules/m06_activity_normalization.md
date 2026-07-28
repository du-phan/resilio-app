# Canonical activity v2

The application persists one provider-neutral `CanonicalActivity`. External
DTOs are validated and mapped at the integration boundary; legacy v1
dictionaries are accepted only by the one-time migration transformer.

The schema stores:

- immutable local ID and active/tombstoned status;
- canonical sport plus exact upstream type/subtype;
- local/UTC occurrence and timezone;
- elapsed/moving seconds, metres, and sensor measurements in SI units;
- notes, perceived effort, device metadata, classification, and segments;
- provider-neutral origin/provenance and sanitized audit fingerprints;
- Resilio-calculated systemic/lower-body load.

RockClimbing and Bouldering map to `climb`. Unknown labels raise a typed
unsupported-sport error. Numeric values are finite and bounded; moving duration
cannot exceed elapsed duration.

External records receive a deterministic `act_i_` hash ID. Historical records
receive a deterministic `act_h_` hash ID. When strict reconciliation links an
external activity to history, the historical local ID is preserved.

Derived kilometres, minutes, pace, weekday, and compatibility presentation
properties are computed views and not duplicated in persisted YAML.

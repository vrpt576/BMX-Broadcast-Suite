# Race-program structure export

BBS can produce a read-only structural snapshot of a RaceManager event for
diagnosing program segments, scoring methods, and combined-class behavior.

Open this URL on the BBS computer:

```text
http://127.0.0.1:8000/api/diagnostics/race-program/export
```

To export a historic event, append its Motoboard ID:

```text
http://127.0.0.1:8000/api/diagnostics/race-program/export?motoboard_id=PASTE-UUID-HERE
```

Save the JSON response when reporting an event-structure problem. The export
contains:

- event, race, and Motoboard identifiers;
- event name/date and race description;
- class identifiers and names;
- displayed moto, round type, round, and motogroup identifiers;
- available stage labels, competition stages, scoring/finalization methods, and inference evidence;
- candidate combined slots;
- the effective event Main-program boundary, its authority, confidence,
  non-authoritative suggestion, and structural evidence; and
- allowlisted schema column names/types for RaceManager structure tables.

The export deliberately excludes rider names, rider IDs, plate numbers,
nicknames, sponsors, credentials, SQL connection strings, application
configuration, and logs. Tests use fixture-only identities and never embed a
real registration export.

This diagnostic describes what BBS currently sees, including a locally stored
operator boundary when one exists. It does not modify RaceManager and importing
an export does not create an override.
See [Program segments and scoring classification](phase-classification.md) for
the documented inference rules and narrowly scoped override format.

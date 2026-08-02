# Main and Overall classification

RaceManager stores both separately raced finals and accumulated-points
classifications in `Round_Type_ID = 1`. BBS therefore uses structural evidence
instead of relabeling every such row as a Main.

The classifier, in priority order, uses:

1. an exact event/class or event/motogroup operator override;
2. multiple classes sharing a final displayed moto (combined Main);
3. a standalone final without a qualifier branch;
4. multiple qualifier motogroups feeding one final;
5. transfer markers;
6. a changed final rider set;
7. a separately numbered final; and
8. same-rider accumulated round scores (Overall).

A same-number, same-rider record with insufficient scoring evidence remains
ambiguous and defaults to Overall for compatibility. The API exposes that
ambiguity through `classification_reason` and `classification_ambiguous`.

## Narrow event override

Only use an override after inspecting the race-program structure export. The
default file is:

```text
data/race_phase_overrides.json
```

For an installed Windows build it resolves beneath:

```text
%ProgramData%\BMX Broadcast Suite\UserData\data
```

Example:

```json
{
  "version": 1,
  "events": {
    "MOTOBOARD-UUID": {
      "classes": {
        "CLASS-UUID": "main"
      },
      "motogroups": {
        "MOTOGROUP-UUID": "overall"
      }
    }
  }
}
```

Allowed values are `main`, `overall`, and `none`. A motogroup override is more
specific than a class override. Overrides apply only to the named Motoboard,
so they cannot silently change another live or historic event.

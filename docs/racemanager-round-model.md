# RaceManager Round Model — v1.2.8

## Why the model changed

Historical state-race data showed that RaceManager does not store every displayed race phase as a simple field attached to one globally unique moto number. The same class can use different moto numbers in qualifier and final branches, and the same moto number can refer to different motogroups in those branches.

BBS therefore treats `Moto_Number` as a display/schedule value, not a stable primary identity.

## Validated branches

### Round type 123 — qualifier progression

The validated qualifier branch stores up to three gate and finish slots on each rider record:

- Round 1: `Lane_1`, `Finish_1`
- Round 2: `Lane_2`, `Finish_2`
- Round 3: `Lane_3`, `Finish_3`

A class can have more than one type-123 motogroup. Each group must remain independently selectable through `Motogroup_DBID`.

### Round type 1 — final classification

The validated type-1 branch contains one final classification for a class:

- final gate: `Lane_1`
- final place: numeric `Finish_1`

BBS labels this stage **Main** when qualifier data contains transfer markers or when the final rider set differs from the qualifier rider set. BBS labels it **Overall** when the same riders complete total-points motos and type 1 represents the final standings.

## Transfer markers

RaceManager uses the string `X` in qualifier finish fields to mark a rider who transferred. BBS exposes that as:

```json
{
  "finish": null,
  "transferred": true,
  "status": "Transfer"
}
```

An `X` is never parsed or sorted as a numeric finishing place.

## Stable stage identity

A resolved broadcast stage contains:

- `motoboard_id`
- `class_id`
- `round_type_id`
- `round_id`
- `motogroup_id`
- `round_index`
- `moto_number` for operator display

This identity prevents qualifier and final records with the same moto number from being merged.

## Dynamic phase programs

`GET /api/current/program` returns the phases BBS can prove for the selected class and qualifier group. The Director rebuilds its phase menu from that response.

Examples:

- transfer class: Round 1, Round 2, Main
- total-points class: Round 1, Round 2, Round 3, Overall

Quarterfinal and semifinal phases remain in the API enum for future compatibility but are not offered unless an exact validated resolver exists.

## Navigation

Next/Previous Moto is branch-aware:

- Round 1/2/3 navigation walks type-123 motogroups.
- Main/Overall navigation walks type-1 classifications.

This prevents a producer pressing Next during mains from accidentally returning to qualifier data.

## Remaining research

The captured state race did not contain a class large enough to produce actual quarterfinals or semifinals. Those mappings remain intentionally unsupported until a suitable historical event can be inspected.

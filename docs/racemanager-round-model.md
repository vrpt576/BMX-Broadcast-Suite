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

BBS classifies this record as either a separately raced final or an accumulated
Total Points classification using the structural evidence and optional
per-event override described in
[Program segments and scoring classification](phase-classification.md).

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

`GET /api/current/program` returns the stages BBS can prove for the selected
class and qualifier group. `GET /api/current/phases` returns the event-wide
phase catalog used by Director, so switching phases remains possible when the
selected class is not present in the target phase.

Examples:

- transfer class: Round 1, Round 2, Main
- total-points class whose third moto is in the final block: Round 1, Round 2, Main
- total-points class with a separate qualifying block: Round 1, Round 2, Round 3

Because the validated RaceManager records do not expose an event-wide Main
start, Director stores an optional boundary by Motoboard ID. The first Transfer
final is displayed only as low-confidence supporting evidence; it is not used
as an automatic range rule. See
[Program segments and scoring classification](phase-classification.md).

Quarterfinal and semifinal phases remain in the API enum for future compatibility but are not offered unless an exact validated resolver exists.

## Navigation

Next/Previous Moto is slot- and branch-aware:

- Round 1/2/3 navigation walks type-123 motogroups.
- Main navigation walks physical final-block race slots. It can use a type-123
  third Total Points moto or a type-1 physical record while retaining a type-1
  accumulated record as the official results source.

This prevents a producer pressing Next during mains from accidentally returning to qualifier data.

Direct moto selection resolves an exact displayed moto within the pinned event
and selected phase. Combined classes sharing that displayed moto remain one
slot. If the requested number is unavailable, the API rejects it and reports
the nearest previous and next numbers rather than silently changing position.

Changing phases first seeks the same selected class or exact combined class
group. Because RaceManager can assign a class a very different displayed moto
in its Main, the numeric moto is allowed to change during this mapping. If no
matching class exists, BBS chooses the nearest target-phase slot and records an
operator-facing navigation message. First/last phase-boundary controls use the
same slot catalog and do not change the pinned event or active graphic.

## Remaining research

The captured state race did not contain a class large enough to produce actual quarterfinals or semifinals. Those mappings remain intentionally unsupported until a suitable historical event can be inspected.

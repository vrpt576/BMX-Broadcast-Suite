# Program segments and scoring classification

BBS keeps four race concepts separate:

- **Program segment** controls Director navigation: Round 1, Round 2,
  Round 3 when separately run, Quarter, Semi, and Main.
- **Competition stage** describes the class occurrence, such as a qualifying
  moto, Main Event, or Total Points final moto.
- **Scoring method** is Transfer, Transfer LST, or Total Points.
- **Finalization method** is a separately raced final or accumulated points.

`Overall` is not a program segment. It can describe a calculated placing or
standing, but it is never shown in the Director round selector and never
creates a navigable gate drop.

## RaceManager evidence

RaceManager stores separately raced finals and accumulated Total Points
classifications in `Round_Type_ID = 1`. BBS uses structural evidence instead
of assuming every such record is a Main Event. The classifier considers, in
priority order:

1. an exact event/class or event/motogroup operator override;
2. multiple classes sharing one physical final moto;
3. a standalone final without a qualifier branch;
4. multiple qualifier motogroups feeding one final;
5. transfer markers;
6. a changed final rider set;
7. a separately numbered final; and
8. same-rider accumulated round scores.

A same-number, same-rider record with insufficient evidence is marked
ambiguous and defaults to Total Points accumulated finalization. The API
exposes `classification_reason` and `classification_ambiguous`.

## Main-program Total Points

The final race block can contain both:

- a Transfer class Main Event (`competition_stage = main_event`); and
- a Total Points class's physical final moto
  (`competition_stage = total_points_final_moto`).

Both use `program_segment = main`. The official accumulated record is attached
as the results source; it does not create an additional race slot. Results use
the accumulated official placing and are labeled **Total Points Results**.

Whether a physical Total Points third moto belongs to Round 3 or Main is an
event running-order decision, not a scoring inference. BBS therefore uses this
evidence hierarchy:

1. an event-scoped operator-confirmed `main_program_start_moto`;
2. a future explicitly validated RaceManager event-boundary field; then
3. unresolved, with the first independently classified Transfer final exposed
   only as a low-confidence suggestion.

The suggestion never changes navigation. Once an operator sets the boundary,
every physical Total Points final moto at or after that displayed number belongs
to Main. This supports TP-only Main programs, TP races before the first Transfer
Main, TP races after the last Transfer Main, interleaving, and number gaps.
Separately raced Transfer finals remain Main races even when the boundary is
unresolved.

### RaceManager boundary fields examined

No reliable event-wide Main start field was present in the validated safe
exports:

- `MB.Motoboard.Has_Mains` confirms that mains exist but has no start number;
- `MB.Rounds.Round_Type_ID` distinguishes branches but stores both separately
  raced finals and calculated Total Points classifications as type 1;
- `Moto_Number_First`, `Moto_Number_Last`, and `Motogroup_Count` are per-class
  round metadata, not an event segment boundary;
- `MB.Motogroups.Moto_Number` is the displayed running-order number but has no
  phase flag;
- `Moto_Key`, `Sub_Moto`, and scramble-related Motogroup fields have no
  validated Main-boundary semantics in the captured events;
- `MB.Age_Classes.Run_Order_Custom`, `Moto_Format_ID`,
  `Transfer_Format_ID`, and `Advance_Type_ID` describe class order or format,
  not the event-wide Main start; and
- maintenance timestamps describe record lifecycle, not gate-drop order.

The service returns the candidate Transfer-final numbers, suggested start,
confidence, and this lack-of-field evidence through the boundary API and safe
diagnostic export.

### Gold Cup / State Race fixture

The 2026-08-01 safe export proves the class and scoring structures around
Motos 27â€“31, but none of the fields above proves where the event changed from
Round 3 to Main. Moto 28 being a Transfer final is supporting evidence only.
The sanitized fixture therefore records an **operator-confirmed** Main start at
Moto 28: Moto 27 remains Round 3, followed by Main Motos 28, 29, 30, and 31.
This also places RaceManager's `5 & Under Intermediate` physical third moto at
Main-program Moto 29 while its type-1 record remains the official accumulated
results source.

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

Use finalization terminology for new entries:

```json
{
  "version": 1,
  "events": {
    "MOTOBOARD-UUID": {
      "main_program_start_moto": 28,
      "classes": {
        "CLASS-UUID": "final_race"
      },
      "motogroups": {
        "MOTOGROUP-UUID": "accumulated_points"
      }
    }
  }
}
```

Allowed new values are `final_race`, `accumulated_points`, and
`total_points`. Legacy `main` and `overall` values remain readable as migration
aliases only; they are translated to finalization methods and never returned
as Director phases. A motogroup override is more specific than a class
override, and every override is scoped to its named Motoboard.

Director exposes **Main program starts at moto** with Save and Reset controls.
It uses:

```text
GET  /api/current/main-program-boundary/{motoboard_id}
PUT  /api/current/main-program-boundary/{motoboard_id}
POST /api/current/main-program-boundary/{motoboard_id}/reset
```

The local JSON file is the only write target; RaceManager SQL remains read-only.

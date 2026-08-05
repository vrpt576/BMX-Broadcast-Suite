# Race slots and combined motos

BBS navigation uses a **race slot** rather than an individual RaceManager
class row. A race slot is one physical scheduled race occurrence in one
selected program segment on one pinned Motoboard.

Its stable key contains:

```text
motoboard-id : program-segment : displayed-moto
```

The slot retains every associated class ID and motogroup ID. If RaceManager
stores two or more classifications for the same displayed moto, BBS presents
one navigation position with a combined class label such as:

```text
Class A / Class B
```

This means:

- Next advances one displayed race slot;
- Previous is the inverse of Next;
- missing numbers are skipped only when the selected segment has no physical slot there;
- Transfer Main events and Total Points final motos remain interleaved in scheduled order;
- an event-scoped Main start determines whether a Total Points third moto is a
  Round 3 or Main slot; Transfer-final ranges are never used as the boundary;
- an accumulated Total Points classification does not create another slot;
- historic Motoboard selection remains pinned; and
- Results Roll uses the same Main-slot ordering and shows a combined moto once.

The persisted current state includes the slot key and its class/motogroup IDs.
Older state files remain valid and are upgraded the next time RaceManager
resolves the selection.

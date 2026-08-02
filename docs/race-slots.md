# Race slots and combined motos

BBS navigation uses a **race slot** rather than an individual RaceManager
class row. A race slot is one displayed moto number in one selected phase on
one pinned Motoboard.

Its stable key contains:

```text
motoboard-id : phase : displayed-moto
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
- missing numbers are skipped only when the selected phase has no slot there;
- an Overall-only number is skipped while navigating Mains;
- historic Motoboard selection remains pinned; and
- Results Roll uses the same Main-slot ordering and shows a combined moto once.

The persisted current state includes the slot key and its class/motogroup IDs.
Older state files remain valid and are upgraded the next time RaceManager
resolves the selection.

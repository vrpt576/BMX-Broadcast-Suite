# Full-program regression fixture: 2026-08-01 Gold Cup / State Race

`tests/fixtures/gold_cup_2026_08_01_full_program.json` is a structural export
of **every** motogroup on the Gold Cup / State Race motoboard
(`6de49ff8-4a40-4eb4-9418-f9349b3e0393`): 62 classes, 65 qualifier motogroups,
62 final records, 600 motogroup-rider rows.

`tests/test_gold_cup_full_walkthrough.py` replays it to step through every
moto of every round the event actually produced, forwards and backwards, and
asserts what the operator reads on the Race Director, the controller and the
OBS overlays.

## Privacy

The export carries **no rider personal data** — no names, bike numbers, ages,
home tracks or sponsors. Each rider is reduced to a stable non-reversible
integer key so that the qualifier/final rider-set comparisons in
`phase_classification_service` behave exactly as they do live. Lane and finish
values are race structure, not identity, and are kept verbatim because the
round-label logic reads them.

## Regenerating it

Read-only, via the `bbs_connector` / `db_datareader` login. Two queries, then
`build` them into the fixture shape (`motogroups[]`, `classes[]`).

Motogroups, one row per group, riders packed into one string
(`rider_key,order,lane_1,lane_2,lane_3,finish_1,finish_2,finish_3`, joined by
`|`):

```sql
SELECT CONCAT(g.Moto_Number,'~',o.Round_Type_ID,'~',g.Motogroup_Number,'~',
       g.Motogroup_DBID,'~',o.Age_Class_ID,'~',o.Round_DBID,'~',
       o.Moto_Number_First,'~',o.Moto_Number_Last,'~',o.Motogroup_Count,'~',
       STRING_AGG(CONCAT(ABS(CHECKSUM(v.Race_Rider_ID)),',',
         p.Motogroup_Rider_Key,',',ISNULL(p.Lane_1,0),',',ISNULL(p.Lane_2,0),',',
         ISNULL(p.Lane_3,0),',',RTRIM(ISNULL(p.Finish_1,'')),',',
         RTRIM(ISNULL(p.Finish_2,'')),',',RTRIM(ISNULL(p.Finish_3,''))),'|')) AS r
FROM MB.Age_Classes a
JOIN MB.Rounds o        ON o.Age_Class_ID = a.Age_Class_DBID
JOIN MB.Motogroups g    ON g.Round_ID = o.Round_DBID
JOIN MB.Motogroup_Riders p ON p.Motogroup_ID = g.Motogroup_DBID
JOIN MB.Racegroup_Riders v ON v.Racegroup_Rider_DBID = p.Racegroup_Rider_ID
WHERE a.Motoboard_ID = ?
GROUP BY g.Motogroup_DBID, o.Age_Class_ID, o.Round_DBID, o.Round_Type_ID,
         o.Moto_Number_First, o.Moto_Number_Last, o.Motogroup_Count,
         g.Moto_Number, g.Motogroup_Number;
```

`ABS(CHECKSUM(...))` is the anonymisation: it collapses the rider GUID to an
integer that is stable within the export (so rider-set equality still works)
and cannot be turned back into a rider.

Classes:

```sql
SELECT a.Age_Class_DBID, a.Class_Name, a.Class_Name_Short,
       a.Moto_Format_ID, a.Transfer_Format_ID
FROM MB.Age_Classes a
WHERE a.Motoboard_ID = ?;
```

Keep the join list identical to `database/queries.py::MOTO_RIDERS_TEMPLATE`
(through `MB.Race_Riders`) so the row count matches what BBS itself reads —
600 for this event, not the 603 rows `MB.Motogroup_Riders` holds on its own.

## What this event looks like

- **Motos 1–27** are Total Points classes. Their `Round_Type_ID = 1` record
  sits on the *same* displayed moto as the qualifier: it is an accumulated
  classification, not a separate race.
- **Motos 28–65** are qualifiers for the classes that run a real final. Those
  finals form the Main program block, displayed motos **28–62** — which is
  why the operator-confirmed Main program start is 28 and why a displayed
  moto number in that range means two different races depending on the
  selected round.
- 19 classes ran a third qualifying moto (`Lane_3` populated); 10 of them are
  Total Points, 9 of them still race a separate Main afterwards.

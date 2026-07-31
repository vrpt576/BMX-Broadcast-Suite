"""Validated read-only SQL queries for USABMX RaceManager.

The joins in this module were verified against RaceManager's RACE database.
RaceManager does not define SQL foreign-key constraints for these relationships,
so keep the joins documented and covered by connector-level tests.
"""

CURRENT_EVENT = """
SELECT TOP 1
    e.Event_DBID AS event_id,
    e.Event_Name AS event_name,
    e.Location AS location,
    e.Date_Begin AS date_begin,
    e.Date_End AS date_end,
    r.Race_DBID AS race_id,
    r.Race_Description AS race_description,
    mb.Motoboard_DBID AS motoboard_id,
    mb.Total_Motos AS total_motos,
    mb.Total_Riders AS total_riders,
    mb.Date_Maintenance AS updated_at
FROM Evt.Events AS e
JOIN Evt.Races AS r
    ON r.Event_ID = e.Event_DBID
JOIN MB.Motoboard AS mb
    ON mb.Race_ID = r.Race_DBID
ORDER BY
    e.Date_Begin DESC,
    mb.Date_Maintenance DESC;
"""

EVENT_BY_MOTOBOARD = """
SELECT TOP 1
    e.Event_DBID AS event_id,
    e.Event_Name AS event_name,
    e.Location AS location,
    e.Date_Begin AS date_begin,
    e.Date_End AS date_end,
    r.Race_DBID AS race_id,
    r.Race_Description AS race_description,
    mb.Motoboard_DBID AS motoboard_id,
    mb.Total_Motos AS total_motos,
    mb.Total_Riders AS total_riders,
    mb.Date_Maintenance AS updated_at
FROM Evt.Events AS e
JOIN Evt.Races AS r
    ON r.Event_ID = e.Event_DBID
JOIN MB.Motoboard AS mb
    ON mb.Race_ID = r.Race_DBID
WHERE mb.Motoboard_DBID = ?;
"""

EVENTS = """
SELECT TOP 250
    e.Event_DBID AS event_id,
    e.Event_Name AS event_name,
    e.Location AS location,
    e.Date_Begin AS date_begin,
    e.Date_End AS date_end,
    r.Race_DBID AS race_id,
    r.Race_Description AS race_description,
    mb.Motoboard_DBID AS motoboard_id,
    mb.Total_Motos AS total_motos,
    mb.Total_Riders AS total_riders,
    mb.Date_Maintenance AS updated_at
FROM Evt.Events AS e
JOIN Evt.Races AS r
    ON r.Event_ID = e.Event_DBID
JOIN MB.Motoboard AS mb
    ON mb.Race_ID = r.Race_DBID
ORDER BY
    e.Date_Begin DESC,
    mb.Date_Maintenance DESC,
    e.Event_Name,
    r.Race_Description;
"""

# RaceManager stores qualifier/moto progression in Round_Type_ID 123 and
# final/overall classification in Round_Type_ID 1.  Do not collapse rows by
# Moto_Number: the two branches may reuse a number for different motogroups.
MOTO_RIDERS_TEMPLATE = """
SELECT
    mg.Moto_Number AS moto_number,
    mg.Motogroup_Number AS motogroup_number,
    mg.Motogroup_DBID AS motogroup_id,
    ac.Age_Class_DBID AS class_id,
    ac.Class_Name AS class_name,
    ac.Class_Name_Short AS class_name_short,
    ro.Round_DBID AS round_id,
    ro.Round_Type_ID AS round_type_id,
    mgr.Motogroup_Rider_DBID AS motogroup_rider_id,
    mgr.Motogroup_Rider_Key AS rider_order,
    mgr.Lane_1 AS lane_1,
    mgr.Lane_2 AS lane_2,
    mgr.Lane_3 AS lane_3,
    mgr.Finish_1 AS finish_1,
    mgr.Finish_2 AS finish_2,
    mgr.Finish_3 AS finish_3,
    mgr.Did_Not_Race AS did_not_race,
    mgr.Date_Maintenance AS updated_at,
    rr.Race_Rider_DBID AS rider_id,
    rr.Bike_Number_Actual AS bike_number,
    rr.First_Name AS first_name,
    rr.Last_Name AS last_name,
    {nickname_expression} AS nickname,
    rr.Proficiency_Code_Act AS proficiency,
    rr.Sponsor AS sponsor
FROM MB.Age_Classes AS ac
JOIN MB.Rounds AS ro
    ON ro.Age_Class_ID = ac.Age_Class_DBID
JOIN MB.Motogroups AS mg
    ON mg.Round_ID = ro.Round_DBID
JOIN MB.Motogroup_Riders AS mgr
    ON mgr.Motogroup_ID = mg.Motogroup_DBID
JOIN MB.Racegroup_Riders AS rgr
    ON rgr.Racegroup_Rider_DBID = mgr.Racegroup_Rider_ID
JOIN MB.Race_Riders AS rr
    ON rr.Race_Rider_DBID = rgr.Race_Rider_ID
WHERE ac.Motoboard_ID = ?
{extra_where}
ORDER BY
    ro.Round_Type_ID,
    mg.Moto_Number,
    mg.Motogroup_Number,
    mgr.Motogroup_Rider_Key;
"""


def moto_riders_query(
    *,
    include_nickname: bool,
    extra_where: str = "",
) -> str:
    """Return a RaceManager rider query compatible with the detected schema."""
    nickname_expression = "rr.Nickname" if include_nickname else "NULL"
    return MOTO_RIDERS_TEMPLATE.format(
        nickname_expression=nickname_expression,
        extra_where=extra_where,
    )


MOTO_RIDERS = moto_riders_query(include_nickname=False)
MOTO_RIDERS_WITH_NICKNAME = moto_riders_query(include_nickname=True)

MOTO_RIDERS_QUALIFIERS = moto_riders_query(
    include_nickname=False,
    extra_where="  AND ro.Round_Type_ID = 123",
)
MOTO_RIDERS_QUALIFIERS_WITH_NICKNAME = moto_riders_query(
    include_nickname=True,
    extra_where="  AND ro.Round_Type_ID = 123",
)

MOTO_RIDERS_BY_NUMBER = moto_riders_query(
    include_nickname=False,
    extra_where="  AND mg.Moto_Number = ?",
)
MOTO_RIDERS_BY_NUMBER_WITH_NICKNAME = moto_riders_query(
    include_nickname=True,
    extra_where="  AND mg.Moto_Number = ?",
)

MOTO_RIDERS_BY_GROUP = moto_riders_query(
    include_nickname=False,
    extra_where="  AND mg.Motogroup_DBID = ?",
)
MOTO_RIDERS_BY_GROUP_WITH_NICKNAME = moto_riders_query(
    include_nickname=True,
    extra_where="  AND mg.Motogroup_DBID = ?",
)

MOTO_RIDERS_BY_CLASS = moto_riders_query(
    include_nickname=False,
    extra_where="  AND ac.Age_Class_DBID = ?",
)
MOTO_RIDERS_BY_CLASS_WITH_NICKNAME = moto_riders_query(
    include_nickname=True,
    extra_where="  AND ac.Age_Class_DBID = ?",
)

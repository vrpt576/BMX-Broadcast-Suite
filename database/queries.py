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

# Round type 123 is RaceManager's staged/current-lineup branch. It retains the
# three lane assignments and receives clipboard-entered finishes.
MOTO_RIDERS = """
SELECT
    mg.Moto_Number AS moto_number,
    mg.Motogroup_Number AS motogroup_number,
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
    rr.Nickname AS nickname,
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
  AND ro.Round_Type_ID = 123
ORDER BY
    mg.Moto_Number,
    mgr.Motogroup_Rider_Key;
"""

MOTO_RIDERS_BY_NUMBER = MOTO_RIDERS.replace(
    "ORDER BY\n    mg.Moto_Number,",
    "  AND mg.Moto_Number = ?\nORDER BY\n    mg.Moto_Number,",
)

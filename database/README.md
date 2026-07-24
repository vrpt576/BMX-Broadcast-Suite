# RaceManager database layer

This directory contains the read-only SQL boundary for USABMX RaceManager.

- `queries.py` contains joins validated against the `RACE` database.
- `racemanager.py` owns short-lived `pyodbc` connections and query execution.
- `racemanager_connector.py` preserves the original import path.

The schema does not define SQL foreign-key constraints for the motoboard tables.
Do not change joins without validating them against a real RaceManager database.
Application/API logic belongs in `connector/`, not this directory.

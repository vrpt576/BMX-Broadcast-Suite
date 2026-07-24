"""Backward-compatible import for the RaceManager database client.

New code should import :class:`database.racemanager.RaceManagerDatabase`.
"""

from database.racemanager import RaceManagerDatabase, RaceManagerDatabaseError

__all__ = ["RaceManagerDatabase", "RaceManagerDatabaseError"]

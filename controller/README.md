# controller

This folder is for the broadcaster control interface and hotkey controller that manages overlay states and live updates.

## Manual current-moto controller

The first controller is served directly by the Connector at `/controller`.
It supports keyboard operation and updates the shared `/api/current` state.
This provides an SCR-ready fallback before automatic moto detection is complete.

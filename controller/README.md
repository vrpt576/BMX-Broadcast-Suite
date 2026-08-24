# controller

This folder is for the broadcaster control interface and hotkey controller that manages overlay states and live updates.

## Manual current-moto controller

The first controller is served directly by the Connector at `/controller`.
It supports keyboard operation and updates the shared `/api/current` state.
This provides an SCR-ready fallback before automatic moto detection is complete.


## Race phases

The manual broadcast state includes Round 1, Round 2, Moto 3, Quarterfinals, Semifinals, and Mains. The third qualifying round is displayed as **Moto 3**; it reads **Main** only for a class that ends on that moto (Total Points, no separately raced final). Use `[` and `]` on the controller page to move between phases, or select a phase directly. The selected phase and moto number are persisted together and shown on the OBS overlay.

- Set the current class name manually and press Enter or **Apply** to publish it with the current moto and round.

## Race Director

The preferred operator interface is now `/director`. It combines race-position
controls, a rider preview, and on-air graphic selection. The original
`/controller` remains available as a compact moto-only controller.

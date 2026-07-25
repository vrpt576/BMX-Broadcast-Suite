# overlay

This folder contains browser-source overlay templates and visual layout assets for OBS.

## Current moto overlay

Add `http://bmxServer01:8000/overlay/current` as an OBS Browser Source. The page
has a transparent background and polls the manual current-moto state four times
per second. A 900 × 180 browser source is a practical starting size.


## Race phases

The manual broadcast state includes Round 1, Round 2, Round 3, Quarterfinals, Semifinals, and Mains. Use `[` and `]` on the controller page to move between phases, or select a phase directly. The selected phase and moto number are persisted together and shown on the OBS overlay.

- The current-moto overlay now shows race phase, class name, and moto number.

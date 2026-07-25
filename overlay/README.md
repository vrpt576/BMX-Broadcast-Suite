# overlay

This folder contains browser-source overlay templates and visual layout assets for OBS.

## Current moto overlay

Add `http://bmxServer01:8000/overlay/current` as an OBS Browser Source. The page
has a transparent background and polls the manual current-moto state four times
per second. A 900 × 180 browser source is a practical starting size.


## Race phases

The manual broadcast state includes Round 1, Round 2, Round 3, Quarterfinals, Semifinals, and Mains. Use `[` and `]` on the controller page to move between phases, or select a phase directly. The selected phase and moto number are persisted together and shown on the OBS overlay.

- The current-moto overlay now shows race phase, class name, and moto number.

## Rider lineup overlay

Use `/overlay/lineup` as an OBS Browser Source. It follows the operator-selected
moto and reads live class, rider, bike-number, and lane data from RaceManager.

Away from the track, use `/overlay/lineup?demo=true` to preview verified sample
data from Moto 1 of the 2026-07-23 Thursday Night Racing event.


## Themes

Both overlays accept a `theme` query parameter:

```text
/overlay/current?theme=default
/overlay/lineup?theme=bend-bmx
/overlay/lineup?demo=true&theme=default
```

Themes are JSON files stored at `themes/<slug>/theme.json`. Copy the `themes/default` folder, choose a new slug, and change the color and typography values to create a track-specific package without changing connector code.

The rider lineup includes labeled columns for **Lane**, **Plate Number**, and **Rider**.

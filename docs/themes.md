# Theme Customization

BBS themes are JSON packages stored in `themes/<slug>/theme.json`. A theme can override only the values it needs; missing values inherit from the default theme. No Python changes are required for a new track color scheme.

## Theme Manager (`/themes`)

For the supported colors and typography below, the in-app Theme Manager at `http://localhost:8000/themes` is the easiest way to edit a theme — no file access or JSON editing required. It covers:

- Listing every installed theme and selecting the active one (writes `BBS_DEFAULT_THEME` via the Configuration API, equivalent to setting it in `.env`).
- Editing the supported color and typography fields with validation — an unsupported key is rejected rather than silently ignored.
- Restoring a theme's supported settings back to BBS defaults.
- Preserving any custom or legacy JSON properties the current editor doesn't expose, so hand-edited `theme.json` files are never silently stripped.

The bundled `default` theme is protected: it can be viewed and selected from the Theme Manager, but not overwritten. Create or copy a custom theme (see below) before saving changes.

Editing themes remotely (saving or restoring defaults through `/themes` from off the BBS host) follows the same admin-token boundary as the rest of remote configuration (`BBS_REMOTE_ADMIN_ENABLED` / `BBS_ADMIN_TOKEN`) — see [Configuration](configuration.md) for the network/security model. *Reading* a theme (`GET /api/themes` and `GET /api/themes/{slug}`) is public read-only broadcast data, not admin-gated — every overlay fetches its active theme's colors client-side from whatever host served the overlay page, so a theme must be readable from any LAN client (an OBS machine, any browser) for LAN-bound overlays to render their configured look instead of silently falling back to the bundled default.

For anything the Theme Manager doesn't yet expose — new color keys, layout, fonts beyond family/transform — edit `theme.json` directly using the reference below; the UI will preserve those additions.

## Select a theme

Set the installation default in `.env`:

```env
BBS_DEFAULT_THEME=my-track
```

Or select a theme for one browser source:

```text
http://localhost:8000/overlay/lineup?theme=my-track&preview=true
```

## Create a theme

Copy the default package and rename the folder using lowercase letters, numbers, hyphens, or underscores:

```bash
cp -r themes/default themes/my-track
```

Edit `themes/my-track/theme.json` and set a matching slug.

## Color fields

- `primary` / `primary_text` — main race-phase, moto, place, and emphasis cells
- `secondary` / `secondary_text` — reserved secondary accent pair for custom layouts and future overlays
- `panel` — main dark overlay surface
- `panel_alt` — column headings and secondary panel surfaces
- `panel_text` — normal text on panels
- `muted_text` — labels and lower-emphasis text
- `header_panel` — class-name header cell
- `row_odd` and `row_even` — alternating lineup/results row backgrounds
- `gate` / `gate_text` — lineup lane cell and its text
- `plate` — rider plate-number text
- `divider` — row and column separator color
- `shadow` — overlay drop shadow
- `warning` / `warning_text` — stale-data and unavailable-data banners

Values may be CSS colors such as hex, `rgb()`, or `rgba()`. Keep enough contrast between each background/text pair for readability over video.

## Example

```json
{
  "name": "My Track",
  "slug": "my-track",
  "colors": {
    "primary": "#00a7e1",
    "primary_text": "#07131c",
    "panel": "#07131c",
    "panel_alt": "#132b3a",
    "panel_text": "#ffffff",
    "header_panel": "#0b2230",
    "row_odd": "rgba(7,19,28,.96)",
    "row_even": "rgba(19,43,58,.96)",
    "gate": "#ffffff",
    "gate_text": "#07131c",
    "plate": "#59d8ff",
    "divider": "rgba(255,255,255,.22)",
    "warning": "#a61b1b",
    "warning_text": "#ffffff"
  },
  "typography": {
    "font_family": "Arial, Helvetica, sans-serif",
    "text_transform": "uppercase"
  }
}
```

Restart is not normally required. Refresh the browser source cache after editing a theme. Test with `?preview=true` before using it live.

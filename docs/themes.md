# Theme Customization

BBS themes are JSON packages stored in `themes/<slug>/theme.json`. A theme can override only the values it needs; missing values inherit from the default theme. No Python changes are required for a new track color scheme.

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

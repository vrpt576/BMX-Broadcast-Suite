# BMX Broadcast Suite Roadmap

This roadmap reflects the project status as of v1.2.3. Priorities may move as more tracks test BBS against their RaceManager installations and live production workflows.

## Shipped

### Foundation and live data
- Read-only RaceManager SQL Server connector
- Current event, motoboard, moto, rider, lane, class, and round data
- Compatibility with optional RaceManager schema fields
- Current-moto, lineup, and experimental results APIs

### Broadcast operation
- OBS browser-source overlays
- Race Director controls and active-graphic state
- WebSocket updates with polling fallback
- Last-known-good lineup resilience
- Configuration, diagnostics, logging, backup, and troubleshooting workflows

### Deployment and branding
- Ubuntu installer and machine-wide `systemd` service
- Start-at-boot, desktop launcher, and system-tray controller
- Track theme packages and expanded v1.2.3 color palette

## Near term

### Theme and overlay polish
- Visual theme editor with live preview and color pickers
- Logo/image placement controls and safe-area guides
- Layout, spacing, font-size, and animation options
- Additional bundled theme examples and accessibility/contrast checks

### Race-day automation
- Optional automatic lineup display when a moto becomes current
- Optional results display after finishes are entered
- Configurable graphic timing, transitions, and producer overrides
- Improved keyboard shortcuts and broadcast status feedback

### Results validation
- Validate transfer, elimination, semifinal, and main-event result selection
- Add event-specific scoring and advancement display rules
- Improve incomplete, provisional, and corrected-result handling

## Mid term

- Rider photos, club logos, sponsor marks, and country/region flags
- Rider lower thirds and introductions
- Live points, rankings, advancement, and qualification graphics
- Timing gate and ProStart integration where data access is available
- Event packages that bundle configuration, themes, and OBS scene guidance
- Multi-track deployment and remote producer workflows

## Later / platform expansion

- Windows background service, desktop launcher, and tray application
- Signed installers and guided upgrades
- Additional race-management platforms where documented integrations are possible
- Public plugin/API contracts for third-party overlays and controllers

## Guiding principles

- Keep RaceManager access read-only
- Favor dependable race-day operation over unnecessary complexity
- Preserve manual producer control even when automation is enabled
- Keep track branding separate from core connector logic
- Validate new race logic at real events before calling it production-ready

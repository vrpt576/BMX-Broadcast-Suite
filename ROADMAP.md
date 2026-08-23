# BMX Broadcast Suite Roadmap

This roadmap reflects the project status as of v1.2.16. Priorities may move as more tracks test BBS against their RaceManager installations and live production workflows.

## Shipped

### Foundation and live data
- Read-only RaceManager SQL Server connector
- Live and historical event/motoboard selection
- Compatibility with optional RaceManager schema fields
- Round-aware stage identity using class, round type, round, motogroup, and round index
- Qualifier (`Round_Type_ID 123`) and final-classification (`Round_Type_ID 1`) resolution
- Transfer-marker normalization and explicit program-segment/scoring-method classification
- Current-moto, lineup, results, and race-program APIs

### Broadcast operation
- OBS browser-source overlays
- Dynamic Race Director phase controls that expose only stages present in RaceManager
- Phase-aware moto movement within qualifier and final branches
- WebSocket updates with polling fallback
- Last-known-good lineup resilience
- Official Main-only results graphic with a server-owned, pausable Results Roll
- Theme-aware Round 1 Break and Main Break graphics
- Configuration, diagnostics, logging, backup, and troubleshooting workflows

### Deployment and branding
- Ubuntu installer and machine-wide `systemd` service
- Start-at-boot, desktop launcher, and system-tray controller
- Windows boot-time background runner, setup wizard, desktop/Start Menu launcher, and notification-area controller
- Track theme packages and expanded color palette

## Near term

### Elimination-round validation
- Capture a historical class large enough to contain real quarterfinals and/or semifinals
- Identify the exact RaceManager tables, round types, group identities, gates, and finishes for those stages
- Add quarterfinal and semifinal resolvers only after the mapping is proven
- Add advancement and bracket-oriented APIs once the source data is understood

### Theme and overlay polish
- Expand the visual theme editor with live preview and color pickers
- Logo/image placement controls and safe-area guides
- Layout, spacing, font-size, and animation options
- Additional bundled theme examples and accessibility/contrast checks

### Race-day automation
- Optional automatic lineup display when a stage becomes current
- Configurable graphic timing, transitions, and producer overrides
- Improved keyboard shortcuts and broadcast status feedback

### Results hardening
- Improve incomplete, provisional, corrected, DNS, and DNF handling
- Add event-specific scoring and advancement display rules
- Continue live validation of transfer and total-points formats

## Mid term

- Rider photos, club logos, sponsor marks, and country/region flags
- Rider lower thirds and introductions
- Live points, rankings, advancement, and qualification graphics
- Timing gate and ProStart integration where data access is available
- Event packages that bundle configuration, themes, and OBS scene guidance
- Multi-track deployment and remote producer workflows

## Later / platform expansion

- Code-signed Windows installer and guided in-place upgrades
- Additional race-management platforms where documented integrations are possible
- Public plugin/API contracts for third-party overlays and controllers

## Guiding principles

- Keep RaceManager access read-only
- Use stable database identities instead of display numbers when identities can collide
- Never invent a round mapping that has not been validated against real RaceManager data
- Favor dependable race-day operation over unnecessary complexity
- Preserve manual producer control even when automation is enabled
- Keep track branding separate from core connector logic

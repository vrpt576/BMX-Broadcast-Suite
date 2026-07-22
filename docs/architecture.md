# BMX Broadcast Suite Architecture

This document describes the planned architecture for BMX Broadcast Suite and the responsibilities of its core components.

## Components

### BBS Connector

The BBS Connector is responsible for connecting to the USABMX RaceManager data source. It translates the external database structure into a normalized internal representation of events, motos, riders, heats, and lane assignments.

Responsibilities:
- Connect securely to the RaceManager SQL Server database
- Validate authentication and connection parameters
- Query active event and moto information
- Provide structured race data to the broadcast engine

### BBS Broadcast Engine

The BBS Broadcast Engine is the central coordination layer. It consumes data from the connector, manages current broadcast state, and exposes the information to overlays and other clients.

Responsibilities:
- Receive normalized race data from the connector
- Manage live broadcast state and current moto selection
- Format data for downstream consumers
- Serve a common JSON/API layer for overlays and themes

### BBS Overlay

The BBS Overlay is the presentation layer used by OBS Studio. It uses browser-source templates to render live graphics, rider lineups, class details, and event information.

Responsibilities:
- Render broadcast data in visually appealing overlays
- Update displays automatically when new data is available
- Support browser-source integration with OBS Studio
- Consume data through the shared JSON/API interface

### BBS Themes

BBS Themes define the visual style and layout for overlays. Themes provide event-specific branding, color palettes, fonts, and layout rules.

Responsibilities:
- Configure visual styling for overlays
- Define layout behavior for different screens and graphics
- Support multiple theme packages for different events or tracks
- Work with the broadcast engine through a shared data contract

## Communication and Integration

All components should communicate through a common JSON/API layer. This establishes a clean contract between the connector, broadcast engine, overlay, and themes.

Why use a common JSON/API layer?

- **Decoupling:** Each component can be developed, tested, and replaced independently.
- **Consistency:** A shared data contract ensures all consumers receive the same structured information.
- **Flexibility:** Overlays and themes can evolve without requiring changes in the connector or engine.
- **Interoperability:** Third-party tools or future extensions can connect to the same API.

## Data Flow

1. The BBS Connector retrieves race data from USABMX RaceManager.
2. The BBS Broadcast Engine normalizes and manages that data.
3. The engine exposes the current broadcast state through a JSON/API layer.
4. BBS Overlay instances consume the API and render live graphics.
5. BBS Themes control presentation details while using the same shared API data.

## Guiding Principles

- Keep component boundaries clear and responsibilities distinct.
- Avoid direct database-to-overlay connections.
- Use the common JSON/API layer as the single source of truth for broadcast data.
- Design for future extensibility and third-party integration.

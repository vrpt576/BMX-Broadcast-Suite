# Frequently Asked Questions

## Can BBS run on a different computer from RaceManager?

Yes, provided it can reach SQL Server over the network and the RaceManager SQL service accepts remote TCP connections.

## Can several OBS computers connect?

Yes. Each can load the same Browser Source URLs. Network and machine capacity determine the practical limit.

## Does BBS modify RaceManager?

The intended deployment uses read-only SQL credentials. BBS reads RaceManager data and keeps its own broadcast state.

## Can BBS keep working during an outage?

It can display the last valid lineup only when the selected moto and race phase match the cached data. It never reuses a lineup for another moto.

## Where are passwords stored?

In the local `.env` file. The configuration API does not return the password. Protect that file and do not commit it.

## Can I create a custom theme?

Yes. Copy a theme directory under `themes/`, give it a new slug, edit `theme.json`, and select that slug in configuration or with `?theme=slug`.

## Is the results overlay production-ready?

Round 1–3 behavior is implemented, but elimination and main fields require live validation.

# OBS Setup Guide

## Recommended Browser Source settings

- Width: 1920
- Height: 1080
- FPS: match the production, commonly 30 or 60
- Shutdown source when not visible: normally off for faster transitions
- Refresh browser when scene becomes active: normally off

## Add a source

In OBS, choose **Sources → + → Browser**, create a source, and enter a BBS overlay URL such as:

`http://BBS-COMPUTER:8000/overlay/current`

Use one source per overlay. Place overlays above camera and video sources. Crop or transform only in OBS; keep the browser's native resolution at 1920×1080.

## Network reliability

Use wired Ethernet where practical. Give the BBS computer a stable DHCP reservation or static address. Test every URL from the OBS computer's normal browser before adding it to OBS.

When OBS shows stale content, right-click the source and choose **Refresh cache of current page**.

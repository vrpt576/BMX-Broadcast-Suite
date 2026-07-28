# OBS Setup Guide

BBS overlays are ordinary OBS Browser Sources served by the connector. Use native OBS Studio with Browser Source support.

## Overlay URLs

Use the BBS server address when OBS is running on another computer. Use `localhost` only when OBS and BBS run on the same computer.

- Current moto: `http://BBS-COMPUTER:8000/overlay/current`
- Rider lineup: `http://BBS-COMPUTER:8000/overlay/lineup`
- Results: `http://BBS-COMPUTER:8000/overlay/results`
- Race controller: `http://BBS-COMPUTER:8000/controller`

Add `?preview=true` while building or testing a scene. Preview mode forces the selected overlay to remain visible even when that graphic is not active in the controller:

`http://BBS-COMPUTER:8000/overlay/lineup?preview=true`

Remove `?preview=true` for live operation so the controller can show and hide the graphic normally.

## Recommended Browser Source settings

- Width: 1920
- Height: 1080
- FPS: match the production, commonly 30 or 60
- Shutdown source when not visible: normally off for faster transitions
- Refresh browser when scene becomes active: normally off
- Browser hardware acceleration: enabled unless the OBS system has a known compatibility issue

## Add a source

In OBS, choose **Sources → + → Browser**, create a source, and enter one overlay URL. Use one source per overlay and place overlays above camera and video sources.

Test every URL in a normal browser on the OBS computer before adding it to OBS. When OBS shows stale or blank content, right-click the source and choose **Refresh cache of current page**.

## Native OBS requirement

If the Browser Source option is missing, remove the Snap package and install native OBS Studio. On Ubuntu:

```bash
sudo snap remove obs-studio
sudo add-apt-repository ppa:obsproject/obs-studio
sudo apt update
sudo apt install -y obs-studio
```

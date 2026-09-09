# BerryControl
![GitHub Downloads (specific asset, all releases)](https://img.shields.io/github/downloads/Yeosangist/BerryControl/berrycontrol?displayAssetName=false&labelColor=%23005500&color=%23008800)

A small GTK/X11 controller for any MPRIS-compatible media player.

## Features

- Minimal floating media widget for MPRIS-compatible players, including browsers and VLC
- Automatically discovers available MPRIS players
- MPRIS state tracking for title and playback state
- Graceful unavailable/connecting/empty-state UI behavior
- Persistent window position in the user config directory
- Native Alt+drag window movement when GTK is available
- Edit window colours and stuff via .config/berrycontrol/window.json file
- Or the Settings...
<sub>Why do I do this to myself</sub>
- System tray icon with window size reset, Settings, and Quit options
<br>

## Install
Dependencies are X11, D-Bus, Python3.10+, PyGObject, GTK3, and AyatanaAppIndicator3.<br>

To build the package:<br>
```bash
pyinstaller --name berrycontrol --windowed --add-data "assets:assets" --noconfirm main.py
```
<br>

To install the desktop entry system-wide:<br>
```bash
sudo cp berrycontrol.desktop /usr/share/applications/
```
<br>

Or for user-only:<br>
```bash
cp berrycontrol.desktop ~/.local/share/applications/
```
<br>

## Notes
I couldn't find any simple floating media controllers for x11 (they all seem to be designed for Wayland), so I made one.<br>
And then overengineered it into oblivion because of course I did :)<br>
Enjoy I guess.

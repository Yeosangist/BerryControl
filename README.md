# BerryControl
![GitHub Downloads (specific asset, all releases)](https://img.shields.io/github/downloads/Yeosangist/BerryControl/berrycontrol?displayAssetName=false&labelColor=%23005500&color=%23008800)

A small GTK/X11 controller for Strawberry's MPRIS interface.

## Features

- Minimal floating media widget for Strawberry
- MPRIS state tracking for title and playback state
- Graceful unavailable/connecting/empty-state UI behavior
- Persistent window position in the user config directory
- Native Alt+drag window movement when GTK is available
- Edit window colours and stuff via .config/berrycontrol/window.json file
- System tray icon with a Quit option
<br>

## Install
To install the desktop entry system-wide:<br>
```bash
sudo cp berrycontrol.desktop /usr/share/applications/
```
<br><br>
Or for user-only:<br>
```bash
cp berrycontrol.desktop ~/.local/share/applications/
```
<br><br>
## Notes
I couldn't find any simple floating media controllers for x11 (they all seem to be designed for Wayland), so I made one.<br>
Currently hardwired to Strawberry Music Player, because that's what I use. If you want something different, you'll need to edit the code.<br><br>
The tray requires the system `AyatanaAppIndicator3` GTK typelib (the`libayatana-appindicator` package on most Linux distributions).


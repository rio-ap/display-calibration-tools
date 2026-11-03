# Display Calibration Tools

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Manual, per-display colour tuning for Linux/X11. The Profile Tuner applies
adjustments live to one XRandR output, then snapshots the exact gamma LUT into
an ICC profile with a `vcgt` tag and assigns it through `colord`.

Repository: <https://github.com/rio-ap/display-calibration-tools>

It is an approximate visual tool, not a colorimeter.

## Install

### 1. Clone or enter the project

```bash
git clone https://github.com/rio-ap/display-calibration-tools.git
cd display-calibration-tools
```

If it is already on your machine:

```bash
cd ~/Projects/Personal/display-calibration-tools
```

### 2. Install the system dependencies

The tool uses system packages, not `pip`.

**Debian / Ubuntu / Linux Mint**

```bash
sudo apt update
sudo apt install python3-gi gir1.2-gtk-3.0 x11-xserver-utils colord libxrandr2 libx11-6
```

**Arch Linux**

```bash
sudo pacman -S python-gobject gtk3 xorg-xrandr colord libxrandr libx11
```

**Fedora**

```bash
sudo dnf install python3-gobject gtk3 xorg-x11-xrandr colord libXrandr libX11
```

Make sure the colord service is running:

```bash
sudo systemctl enable --now colord
```

You also need a desktop colour manager that applies display profiles:

- Cinnamon: `csd-color` (included with Cinnamon)
- GNOME: `gsd-color` (part of `gnome-settings-daemon`)
- KDE: `colord-kde`

### 3. Check the machine

```bash
python3 check_deps.py
```

A ready machine prints:

```text
[PASS] Python 3.12
[PASS] X11 session
[PASS] xrandr
[PASS] libX11
[PASS] libXrandr
[PASS] PyGObject + GTK3
[PASS] colord reports display devices
[PASS] desktop colour manager: csd-color

Result: ready. Run: python3 profile_tuner.py
```

If any line says `[FAIL]`, fix it using the troubleshooting table below before
opening the GUI.

### 4. Run it

```bash
python3 profile_tuner.py
```

The **Target display** dropdown lists every connected output. It defaults to
the internal panel, then the primary output. You can also select explicitly:

```bash
python3 profile_tuner.py --output eDP-1
python3 profile_tuner.py --output DP-2
```

### X11 only

This tool requires an **X11/Xorg** session. It does not work on native Wayland.
On a Wayland desktop, log out and choose an “Xorg” or “Cinnamon on X11” session
at the login screen.

### AI agent quick start

1. Read [AGENTS.md](AGENTS.md).
2. Run `python3 check_deps.py`.
3. Inspect displays with `xrandr --query` and `colormgr get-devices`.
4. Run `python3 profile_tuner.py --output <output>`.
5. If the native EDID profile is not found, pass `--source-profile`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `No module named 'gi'` | Install `python3-gi`. |
| `Namespace Gtk not available` | Install `gir1.2-gtk-3.0`. |
| `xrandr: command not found` | Install `x11-xserver-utils` (Debian/Mint), `xorg-xrandr` (Arch), or `xorg-x11-xrandr` (Fedora). |
| `libXrandr` not found | Install `libxrandr2` or `libXrandr`. |
| `colormgr: command not found` | Install `colord`, then `sudo systemctl enable --now colord`. |
| `colord reports no display devices` | Log into a graphical X11 session; ensure colord is running. |
| `no known desktop colour manager` | Enable `csd-color`, `gsd-color`, or `colord-kde` for your desktop. Live preview may work, but login persistence may not. |
| `output ... is not connected` | Run `xrandr --query` and use the exact output name with `--output`. |
| `no EDID profile found` | Pass `--source-profile /path/to/edid-profile.icc`; do not use a profile that already has a `vcgt` tag. |
| GUI opens but the screen does nothing | Check `XDG_SESSION_TYPE`; use X11, not Wayland. |
| Profile does not survive logout | Check the desktop colour manager and `colormgr device-get-default-profile`. |
| Permission or display error | Do not run the GUI with `sudo`; run it as your logged-in user. |

## Profile Tuner

The **Target display** dropdown lists every connected output. It defaults to the
internal panel, then the primary output. You can also select explicitly:

```bash
python3 profile_tuner.py --output eDP-1
python3 profile_tuner.py --output DP-2
```

Each display gets its own profile file:

- `eDP-1` keeps `~/.local/share/icc/laptop-color-reference.icc` if it already
  exists.
- Other outputs use
  `~/.local/share/icc/manual-calibration-<sanitized-output>.icc`.

### Basic tab

- Temperature
- Tint
- Brightness
- Contrast
- Gamma

### Advanced tab

- Red / green / blue gain
- Red / green / blue gamma
- Red / green / blue black lift
- Gamma curve preview

### Buttons

- **Reset** — restores the selected display's saved profile LUT.
- **Test Pattern** — opens white/gray/red/green/blue/`#a10f0f` patches on the
  selected display. Press **Esc** or click **Close** to dismiss.
- **Save & Apply Profile** — snapshots the current LUT into the selected
  display's ICC profile and assigns it through `colord`.

Closing the window restores the last saved LUT. No autostart script is used; the
desktop colour manager (`csd-color`, `gsd-color`, or `colord-kde`) applies the
assigned profile at login.

## AI agent guide

See [AGENTS.md](AGENTS.md) for a machine-by-machine adaptation procedure:
inspecting the session, finding the target output, discovering the native EDID
profile, installing dependencies, verifying persistence, and safety rules.

## Legacy CTM tuner

`laptop_color_tuner.py` is the earlier 3-slider CTM tool. It is kept for
reference, but `profile_tuner.py` is the better path because its result can be
stored in the profile and survives without a startup script.

## Profile builder

`make_profile.py` can also generate a profile directly from the saved gains in
`~/.config/laptop-color-tuner/last.json`:

```bash
python3 make_profile.py
```

This legacy builder is aimed at the original `eDP-1` setup. Use the GUI for other
outputs.

## Portability

Tested on Linux Mint 22.3 Cinnamon, X11, Intel graphics, with an AOC 22B2WG5 as
the reference display.

Current requirements:

- Linux with an X11 session and XRandR gamma support
- `colord` plus a desktop colour manager that applies display profiles
- Python 3 with PyGObject/GTK3
- `xrandr` and `libXrandr.so.2`

Output selection and native EDID profile discovery are automatic, with
`--output` and `--source-profile` overrides. Native Wayland, macOS, and Windows
are not supported. A standard display VCGT profile is per-channel; it cannot
represent cross-channel saturation or hue changes.

Generated profiles are unit-specific. Do not share one as a universal profile
for another panel.

## License

MIT. See [LICENSE](LICENSE).

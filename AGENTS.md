# Agent Guide

This file is for an AI coding agent adapting these tools to another Linux
machine. Read it before changing code or applying a profile.

## What this project does

It provides a manual, per-display colour tuner:

1. Read the current XRandR gamma LUT for one output.
2. Let the user adjust that LUT live with a GTK3 GUI.
3. Snapshot the exact LUT into an ICC profile with a `vcgt` tag.
4. Import and assign that profile through `colord` so the desktop colour
   manager reapplies it at login.

It is **not** a colorimeter and does not measure the panel. It is an
approximate visual tool. It cannot add gamut, and a standard display VCGT
profile cannot represent cross-channel saturation or hue changes.

## Tested environment

- Linux Mint 22.3 Cinnamon
- X11 session (`XDG_SESSION_TYPE=x11`)
- Intel Iris Xe graphics
- `eDP-1` internal laptop panel
- `DP-2` AOC 22B2WG5 external reference
- Python 3, PyGObject/GTK3, `xrandr`, `colord`, `csd-color`

Do not assume the current output name, EDID profile path, or desktop colour
manager on another machine.

## Phase 1: inspect, do not guess

Run these first and report what they show:

```bash
echo "session=$XDG_SESSION_TYPE desktop=$XDG_CURRENT_DESKTOP"
xrandr --query
python3 -c "import monitors; print(monitors.list_monitors())"
colormgr get-devices
ps -ef | grep -E 'csd-color|colord' | grep -v grep
```

Expected:

- `XDG_SESSION_TYPE` must be `x11`.
- `xrandr --query` lists connected outputs with geometry.
- `monitors.list_monitors()` identifies internal outputs (`eDP-*`, `LVDS-*`,
  `DSI-*`, `DPI-*`) and primary outputs.
- `colormgr get-devices` shows one block per display. Each block has
  `XRANDR_name=<output>`, `OutputEdidMd5=<hash>`, and profile filenames.

If the session is Wayland, stop. Native Wayland compositors generally do not
expose a global gamma LUT; XWayland is not a reliable substitute.

## Phase 2: choose the target display

The tool defaults to the internal panel, then the primary output. The GUI also
has a **Target display** dropdown. For scripts:

```bash
python3 profile_tuner.py --output eDP-1
python3 profile_tuner.py --output DP-2
```

Use `monitors.resolve_output()` when writing new code. Never apply a profile to
the reference monitor unless the user explicitly asks for that.

## Phase 3: find the native EDID profile

The generated profile must be based on the target panel's **EDID-derived**
profile, not on another custom/calibrated profile. Stacking two corrections
will produce the wrong result.

```bash
python3 -c "import make_profile; print(make_profile.find_native_profile('eDP-1'))"
```

`find_native_profile` matches `OutputEdidMd5` to the `edid-<hash>.icc` file in
the colord device block. If it returns `None`, pass an explicit source:

```bash
python3 profile_tuner.py --output DP-2 --source-profile /path/to/edid-profile.icc
```

Do not pass a profile that already has a `vcgt` tag or a custom calibration as
the source.

## Phase 4: install dependencies

Debian/Ubuntu/Mint:

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 x11-xserver-utils colord
```

The runtime also needs `libX11.so.6` and `libXrandr.so.2`, normally present.
No pip packages are required.

The persistence path needs `colord` and a desktop colour manager that loads
profiles. On Cinnamon this is `csd-color`; on GNOME it is `gsd-color`; KDE has
`colord-kde`. Verify the manager is running before promising persistence.

## Phase 5: run and tune

```bash
cd ~/Projects/Personal/manual-calibration-tools
python3 profile_tuner.py
```

Use the target dropdown to select the display. Adjust sliders. Use **Test
Pattern** on the target display. Press **Save & Apply Profile** when satisfied.

Profile paths:

- `eDP-1` keeps the legacy `~/.local/share/icc/laptop-color-reference.icc` if it
  already exists.
- Other outputs use
  `~/.local/share/icc/manual-calibration-<sanitized-output>.icc`.

A profile is per-panel. Never copy one display's profile to another display.

## Phase 6: verify persistence

```bash
python3 - <<'PY'
import xrandr_gamma
r, g, b = xrandr_gamma.get_lut("eDP-1")
print(len(r), r[-1], g[-1], b[-1])
PY

colormgr device-get-default-profile \
  '/org/freedesktop/ColorManager/devices/xrandr_Communications_Supply_Corporation__A_division_of_WESCO__trazire_1000'
```

Look for:

- `Gamma Table: Yes`
- `Filename:` pointing at the generated profile
- The live LUT values matching the generated profile's `vcgt` values

There should be **no autostart script** for this project. The profile is loaded
by `colord`/the desktop colour manager.

## Safety rules

- Target one output at a time.
- Do not modify the EDID or the system ICC profiles.
- Back up the current profile before replacing it.
- Do not run the GUI as root.
- Do not delete profiles without identifying which device owns them.
- Revert by assigning the native EDID profile:
  `colormgr device-make-profile-default <device> <edid-profile>`.
- Large gain/gamma changes can clip colours; use small steps and check the test
  pattern.
- Do not claim the result is colorimetrically accurate.

## Code map

- `monitors.py` — parse `xrandr --query`, detect internal/primary outputs.
- `xrandr_gamma.py` — ctypes XRandR gamma LUT read/write.
  Important: use `XRRAllocGamma` for the setter. Separately allocated channel
  arrays corrupt the green/blue tables.
- `make_profile.py` — ICC tag construction, `find_native_profile`,
  `source_profile_for`, `build_profile_from_luts`.
- `profile_install.py` — import/replace/assign a profile through `colord`.
- `profile_tuner.py` — GTK3 GUI, per-channel LUT tuning, profile snapshot.
- `laptop_color_tuner.py` — legacy CTM tool; not recommended for new setups.
- `test_*.py` — unit tests.

## Adapting to another machine

1. Clone the repo.
2. Run Phase 1 and report the actual session, outputs, and colour manager.
3. Install the dependencies.
4. Choose the target output; do not hardcode `eDP-1` in new code.
5. If `find_native_profile` returns `None`, get the native EDID profile path
   from colord or ask the user for it.
6. Test on one output only.
7. Save and verify the profile; confirm `Gamma Table: Yes`.
8. Ensure no autostart script was added.
9. Run the tests:
   `python3 -m unittest -v test_monitors.py test_profile_tuner.py test_make_profile.py test_laptop_color_tuner.py`
10. Update the README/portability notes if behavior changes.

## What not to promise

- Universal Windows/macOS support.
- Native Wayland support.
- Colorimeter-level accuracy.
- A cross-platform or cross-panel working ICC profile.
- Matching a wide-gamut reference monitor on a lower-gamut panel beyond the
  panel's physical gamut.

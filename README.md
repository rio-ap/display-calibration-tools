# Manual Calibration Tools

Manual, per-display colour tuning for Linux/X11. The Profile Tuner applies
adjustments live to one XRandR output, then snapshots the exact gamma LUT into
an ICC profile with a `vcgt` tag and assigns it through `colord`.

It is an approximate visual tool, not a colorimeter.

## Profile Tuner

```bash
cd ~/Projects/Personal/manual-calibration-tools
python3 profile_tuner.py
```

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

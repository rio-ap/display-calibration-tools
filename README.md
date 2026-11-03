# Laptop Color Tuner

Tools for visually tuning the **eDP-1 laptop panel** against the AOC reference
monitor. The AOC (`DP-2`) is never touched.

## Profile Tuner (recommended)

```bash
cd ~/Projects/Personal/manual-callibration-tools
python3 profile_tuner.py
```

This is the per-channel profile editor. It applies adjustments live to the
laptop's XRandR gamma LUT and can snapshot the exact result into an ICC profile.

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

- **Reset** — restores the saved profile's LUT.
- **Test Pattern** — laptop-only white/gray/red/green/blue/`#a10f0f` patches.
  Press **Esc** or click **Close** to dismiss.
- **Save & Apply Profile** — snapshots the current LUT into:

  ```text
  ~/.local/share/icc/laptop-color-reference.icc
  ```

  and assigns it to `eDP-1` through `colord`.

Closing the window restores the last saved profile LUT. No autostart script is
used; `colord` / `csd-color` applies the assigned profile at login.

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

## Notes

This is an approximate visual tool, not a colorimeter calibration. A standard
display profile/VCGT can represent per-channel gain, gamma, and black-level
curves. It cannot represent cross-channel saturation or hue changes; those need
a 3D LUT or the XRandR CTM path.

## Portability

Tested on Linux Mint 22.3 Cinnamon, X11, Intel graphics, with an AOC 22B2WG5 as
the reference display.

Current assumptions that need changing before this is universal:

- The output name is hardcoded as `eDP-1`.
- The source EDID profile is hardcoded to this laptop's
  `edid-1eec840f5baccc8e533ba13fc2fb3e33.icc`.
- It requires X11 + XRandR gamma support. It does not work on a native Wayland
  session.
- It uses `colord` and `csd-color` to persist the profile. Other desktops need a
  compatible color manager.
- It needs Python 3 with PyGObject/GTK3.

The core XRandR LUT code is portable across Linux X11 systems once the output
name and source profile are configurable.

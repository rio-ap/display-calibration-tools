# Laptop Color Tuner

Small GTK3 tool for visually tuning the **eDP-1 laptop panel** against the AOC
reference monitor.

It applies a temporary 3x3 colour matrix through XRandR to `eDP-1` only. The AOC
(`DP-2`) is never touched.

## Run

```bash
cd ~/laptop-color-tuner
python3 laptop_color_tuner.py
```

## Controls

- **Red / Green / Blue gain** — shifts the white balance of the laptop panel.
- **Saturation** — makes colours more or less saturated; use small changes.
- **Reset** — restores the identity matrix.
- **Test Pattern** — opens a laptop-only pattern with white, gray, red, green,
  blue, and the wallpaper's `#a10f0f` patch. Press **Esc** or click **Close** to
  dismiss it.
- **Save Reference** — writes the current gains, saturation, matrix, and
  raw CTM values to:

  ```
  ~/.config/laptop-color-tuner/last.json
  ```

Closing the window resets `eDP-1` to identity. The saved JSON remains.

## Generate the persistent profile

`make_profile.py` reads the saved gains from `last.json` and writes a synthetic
ICC profile with a VCGT calibration table:

```bash
cd ~/laptop-color-tuner
python3 make_profile.py
```

The profile is written to:

```text
~/.local/share/icc/laptop-color-reference.icc
```

It is assigned to `eDP-1` through `colord`; `csd-color` applies its gamma table
at login. No autostart script is used.

## Notes

This is an approximate visual tool, not a colorimeter calibration. The matrix is
applied in the display pipeline without a measured profile, so large changes can
distort colours. The generated profile can represent per-channel gain/gamma
corrections; cross-channel matrices and saturation boosts cannot be represented
in a standard display VCGT profile.

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

## Reapply at login

`apply_saved.py` reads `last.json` and reapplies the saved matrix to `eDP-1`.
It is installed as `~/.local/bin/laptop-color-apply` and started by
`~/.config/autostart/laptop-color-reference.desktop`.

The script retries briefly while Cinnamon is setting up the displays, and logs
to `~/.config/laptop-color-tuner/apply.log`.

## Notes

This is an approximate visual tool, not a colorimeter calibration. The matrix is
applied in the display pipeline without a measured profile, so large changes can
distort colours. Use it to find a reference setting, then persist that setting
with a startup script or a proper ICC/VCGT calibration.

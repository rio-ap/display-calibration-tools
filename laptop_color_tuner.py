#!/usr/bin/env python3
"""Temporary per-output colour tuning for the eDP-1 laptop panel.

The sliders adjust a 3x3 colour matrix applied with xrandr to eDP-1 only.
This is an approximate visual tuning tool, not a colorimetric calibration.
Closing the window resets eDP-1 to the identity matrix.
"""

from __future__ import annotations

import atexit
import datetime
import json
import os
import re
import subprocess
import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

OUTPUT = "eDP-1"
APP_NAME = "Laptop Color Tuner"
CONFIG_DIR = os.path.expanduser("~/.config/laptop-color-tuner")
SAVE_PATH = os.path.join(CONFIG_DIR, "last.json")

IDENTITY = [
    [1.0, 0.0, 0.0],
    [0.0, 1.0, 0.0],
    [0.0, 0.0, 1.0],
]

# Rec. 709 luma coefficients, used by the saturation matrix.
LUMA = (0.2126, 0.7152, 0.0722)


def gains_matrix(red: float, green: float, blue: float) -> list[list[float]]:
    return [
        [red, 0.0, 0.0],
        [0.0, green, 0.0],
        [0.0, 0.0, blue],
    ]


def saturation_matrix(saturation: float) -> list[list[float]]:
    """Identity at 1.0, grayscale at 0.0, more saturated above 1.0."""
    inv = 1.0 - saturation
    lr, lg, lb = LUMA
    return [
        [lr * inv + saturation, lg * inv, lb * inv],
        [lr * inv, lg * inv + saturation, lb * inv],
        [lr * inv, lg * inv, lb * inv + saturation],
    ]


def matmul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [
        [sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)]
        for i in range(3)
    ]


def compute_matrix(red: float, green: float, blue: float, saturation: float) -> list[list[float]]:
    """Apply per-channel gains first, then the saturation matrix."""
    return matmul(saturation_matrix(saturation), gains_matrix(red, green, blue))


def to_fixed(value: float) -> tuple[int, int]:
    """Convert to the S31.32 fixed-point pair expected by the DRM CTM property.

    XRandR exposes each 64-bit CTM element as two 32-bit integers, low word
    first. The property itself is unsigned 32-bit, so negative values wrap.
    """
    raw = int(round(value * (1 << 32))) & ((1 << 64) - 1)
    return raw & 0xFFFFFFFF, (raw >> 32) & 0xFFFFFFFF


def ctm_values(matrix: list[list[float]]) -> list[int]:
    values: list[int] = []
    for row in matrix:
        for value in row:
            values.extend(to_fixed(value))
    return values


def ctm_string(matrix: list[list[float]]) -> str:
    return ",".join(str(value) for value in ctm_values(matrix))


def run_xrandr(extra_args: list[str]) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        ["xrandr", "--output", OUTPUT, *extra_args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        message = (proc.stderr or proc.stdout or "xrandr failed").strip()
        raise RuntimeError(message)
    return proc


def apply_matrix(matrix: list[list[float]]) -> None:
    run_xrandr(["--set", "CTM", ctm_string(matrix)])


def reset_output() -> None:
    apply_matrix(IDENTITY)


def reset_output_silent() -> None:
    try:
        reset_output()
    except Exception:
        pass


def get_output_geometry(output: str = OUTPUT) -> tuple[int, int, int, int]:
    """Return x, y, width, height for an xrandr output."""
    try:
        query = subprocess.check_output(["xrandr", "--query"], text=True)
    except Exception:
        return 0, 0, 1920, 1080
    pattern = re.compile(
        rf"^{re.escape(output)} connected(?: primary)? (\d+)x(\d+)\+(\d+)\+(\d+)",
        re.MULTILINE,
    )
    match = pattern.search(query)
    if not match:
        return 0, 0, 1920, 1080
    width, height, x, y = (int(part) for part in match.groups())
    return x, y, width, height


class ColorPatch(Gtk.DrawingArea):
    def __init__(self, label: str, color: str, text_color: str) -> None:
        super().__init__()
        self.label = label
        self.color = self._parse_color(color)
        self.text_color = self._parse_color(text_color)
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.connect("draw", self.on_draw)

    @staticmethod
    def _parse_color(value: str) -> tuple[float, float, float]:
        value = value.lstrip("#")
        return tuple(int(value[i : i + 2], 16) / 255.0 for i in (0, 2, 4))

    def on_draw(self, widget: Gtk.Widget, cr: object) -> bool:
        width = widget.get_allocated_width()
        height = widget.get_allocated_height()
        cr.set_source_rgb(*self.color)
        cr.rectangle(0, 0, width, height)
        cr.fill()
        cr.set_source_rgb(*self.text_color)
        cr.select_font_face("Sans")
        cr.set_font_size(26)
        extents = cr.text_extents(self.label)
        cr.move_to(
            (width - extents.width) / 2,
            (height + extents.height) / 2,
        )
        cr.show_text(self.label)
        return False


class TestPatternWindow(Gtk.Window):
    def __init__(self, parent: Gtk.Window) -> None:
        super().__init__(title="Laptop test pattern")
        self.set_transient_for(parent)
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_can_focus(True)
        self.connect("key-press-event", self.on_key_press)

        x, y, width, height = get_output_geometry()
        self.set_default_size(width, height)
        self.move(x, y)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(outer)

        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bar.set_border_width(6)
        title = Gtk.Label(label="Test pattern — press Esc or click Close")
        title.set_xalign(0)
        bar.pack_start(title, True, True, 0)
        close = Gtk.Button(label="Close")
        close.connect("clicked", lambda *_: self.destroy())
        bar.pack_end(close, False, False, 0)
        outer.pack_start(bar, False, False, 0)

        grid = Gtk.Grid()
        grid.set_row_homogeneous(True)
        grid.set_column_homogeneous(True)
        outer.pack_start(grid, True, True, 0)

        patches = [
            ("White", "#ffffff", "#000000"),
            ("50% Gray", "#808080", "#ffffff"),
            ("Red", "#ff0000", "#ffffff"),
            ("Green", "#00ff00", "#000000"),
            ("Blue", "#0000ff", "#ffffff"),
            ("Wallpaper #a10f0f", "#a10f0f", "#ffffff"),
        ]
        for index, (label, color, text_color) in enumerate(patches):
            grid.attach(ColorPatch(label, color, text_color), index % 2, index // 2, 1, 1)

    def on_key_press(self, _widget: Gtk.Widget, event: Gdk.EventKey) -> bool:
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()
            return True
        return False


class TunerWindow(Gtk.Window):
    def __init__(self) -> None:
        super().__init__(title=APP_NAME)
        self.set_border_width(14)
        self.set_default_size(640, 430)
        self.set_resizable(False)

        self._updating = False
        self._pending: int | None = None
        self._test_window: TestPatternWindow | None = None
        self._last_matrix = [row[:] for row in IDENTITY]

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(outer)

        heading = Gtk.Label()
        heading.set_markup("<b>Laptop Color Tuner</b>")
        heading.set_xalign(0)
        outer.pack_start(heading, False, False, 0)

        subtitle = Gtk.Label(
            label="Live preview on eDP-1 only. Closing resets to identity."
        )
        subtitle.set_xalign(0)
        subtitle.set_line_wrap(True)
        outer.pack_start(subtitle, False, False, 0)

        grid = Gtk.Grid(column_spacing=10, row_spacing=8)
        outer.pack_start(grid, False, False, 0)

        self.controls: dict[str, tuple[Gtk.Scale, Gtk.Label]] = {}
        rows = [
            ("red", "Red gain", 0.80, 1.20, 1.00),
            ("green", "Green gain", 0.80, 1.20, 1.00),
            ("blue", "Blue gain", 0.80, 1.20, 1.00),
            ("saturation", "Saturation", 0.80, 1.30, 1.00),
        ]

        for row_index, (key, label_text, low, high, default) in enumerate(rows):
            label = Gtk.Label(label=label_text)
            label.set_xalign(0)
            grid.attach(label, 0, row_index, 1, 1)

            scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, low, high, 0.01)
            scale.set_value(default)
            scale.set_digits(2)
            scale.set_hexpand(True)
            scale.set_size_request(320, -1)
            scale.connect("value-changed", self.on_scale_changed)
            grid.attach(scale, 1, row_index, 1, 1)

            value_label = Gtk.Label(label=f"{default:.2f}")
            value_label.set_width_chars(5)
            value_label.set_xalign(1)
            grid.attach(value_label, 2, row_index, 1, 1)
            self.controls[key] = (scale, value_label)

        note = Gtk.Label(
            label=(
                "The sliders are approximate. Use small changes; the matrix is "
                "applied in the display pipeline, not as a measured profile."
            )
        )
        note.set_xalign(0)
        note.set_line_wrap(True)
        note.set_max_width_chars(70)
        outer.pack_start(note, False, False, 0)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        outer.pack_start(buttons, False, False, 0)

        reset = Gtk.Button(label="Reset")
        reset.connect("clicked", self.on_reset)
        buttons.pack_start(reset, False, False, 0)

        pattern = Gtk.Button(label="Test Pattern")
        pattern.connect("clicked", self.on_test_pattern)
        buttons.pack_start(pattern, False, False, 0)

        save = Gtk.Button(label="Save Reference")
        save.connect("clicked", self.on_save)
        buttons.pack_end(save, False, False, 0)

        self.status = Gtk.Label(label="")
        self.status.set_xalign(0)
        self.status.set_line_wrap(True)
        self.status.set_max_width_chars(70)
        outer.pack_start(self.status, False, False, 0)

        self.connect("destroy", self.on_destroy)

        try:
            reset_output()
            self.set_status("Ready — identity applied to eDP-1")
        except Exception as exc:
            self.set_status(f"ERROR: could not reset eDP-1: {exc}")

    def read_values(self) -> dict[str, float]:
        return {key: self.controls[key][0].get_value() for key in self.controls}

    def set_status(self, text: str) -> None:
        self.status.set_text(text)

    def on_scale_changed(self, _scale: Gtk.Scale) -> None:
        if self._updating:
            return
        for scale, value_label in self.controls.values():
            value_label.set_text(f"{scale.get_value():.2f}")
        self.schedule_apply()

    def schedule_apply(self) -> None:
        if self._pending is not None:
            GLib.source_remove(self._pending)
        self._pending = GLib.timeout_add(35, self.apply_current)

    def apply_current(self) -> bool:
        self._pending = None
        values = self.read_values()
        matrix = compute_matrix(
            values["red"],
            values["green"],
            values["blue"],
            values["saturation"],
        )
        try:
            apply_matrix(matrix)
        except Exception as exc:
            self.set_status(f"ERROR: {exc}")
            return False
        self._last_matrix = matrix
        self.set_status(
            "Applied to eDP-1 — "
            f"R {values['red']:.2f}, G {values['green']:.2f}, "
            f"B {values['blue']:.2f}, Sat {values['saturation']:.2f}"
        )
        return False

    def on_reset(self, _button: Gtk.Button) -> None:
        self._updating = True
        for scale, value_label in self.controls.values():
            scale.set_value(1.0)
            value_label.set_text("1.00")
        self._updating = False
        self.schedule_apply()

    def on_test_pattern(self, _button: Gtk.Button) -> None:
        if self._test_window is not None:
            self._test_window.present()
            return
        self._test_window = TestPatternWindow(self)
        self._test_window.connect("destroy", self.on_test_destroyed)
        self._test_window.show_all()
        self._test_window.present()

    def on_test_destroyed(self, _widget: Gtk.Widget) -> None:
        self._test_window = None

    def on_save(self, _button: Gtk.Button) -> None:
        values = self.read_values()
        matrix = compute_matrix(
            values["red"],
            values["green"],
            values["blue"],
            values["saturation"],
        )
        data = {
            "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
            "output": OUTPUT,
            "gains": {
                "red": values["red"],
                "green": values["green"],
                "blue": values["blue"],
            },
            "saturation": values["saturation"],
            "matrix": matrix,
            "ctm": ctm_values(matrix),
        }
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(SAVE_PATH, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2)
                handle.write("\n")
        except OSError as exc:
            self.set_status(f"ERROR: could not save reference: {exc}")
            return
        self.set_status(f"Saved reference to {SAVE_PATH}")

    def place_main_window(self) -> bool:
        x, y, width, height = get_output_geometry()
        win_width, win_height = self.get_size()
        self.move(
            x + max(30, (width - win_width) // 2),
            y + max(30, (height - win_height) // 2),
        )
        return False

    def on_destroy(self, _widget: Gtk.Widget) -> None:
        if self._pending is not None:
            GLib.source_remove(self._pending)
            self._pending = None
        reset_output_silent()
        Gtk.main_quit()


def main() -> int:
    atexit.register(reset_output_silent)
    window = TunerWindow()
    window.show_all()
    GLib.timeout_add(150, window.place_main_window)
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())

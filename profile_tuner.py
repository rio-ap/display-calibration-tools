#!/usr/bin/python3
"""Per-channel profile tuner for the eDP-1 laptop panel.

The preview writes the XRandR gamma LUT directly. Saving snapshots that exact
LUT into an ICC profile with a VCGT tag and assigns it through colord.
"""

from __future__ import annotations

import os
import subprocess
import sys

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

import make_profile  # noqa: E402
import profile_install  # noqa: E402
import xrandr_gamma  # noqa: E402
from laptop_color_tuner import TestPatternWindow, get_output_geometry  # noqa: E402

OUTPUT = "eDP-1"
PROFILE_PATH = os.path.expanduser("~/.local/share/icc/laptop-color-reference.icc")
IDENTITY_CTM = "0,1,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,1"


def identity_lut(size: int = 1024) -> list[int]:
    return [round(index * 65535 / (size - 1)) for index in range(size)]


def channel_lut(
    base: list[int],
    gain: float,
    gamma: float,
    contrast: float,
    black_lift: float,
) -> list[int]:
    result: list[int] = []
    for value in base:
        normalized = max(0.0, min(1.0, value / 65535.0))
        adjusted = normalized ** gamma
        adjusted = (adjusted - 0.5) * contrast + 0.5
        adjusted *= gain
        adjusted = black_lift + (1.0 - black_lift) * adjusted
        adjusted = max(0.0, min(1.0, adjusted))
        result.append(round(adjusted * 65535))
    return result


class CurveView(Gtk.DrawingArea):
    def __init__(self) -> None:
        super().__init__()
        self.set_size_request(620, 180)
        self._luts: tuple[list[int], list[int], list[int]] | None = None
        self.connect("draw", self.on_draw)

    def set_luts(self, red: list[int], green: list[int], blue: list[int]) -> None:
        self._luts = (red, green, blue)
        self.queue_draw()

    def on_draw(self, widget: Gtk.Widget, cr: object) -> bool:
        width = widget.get_allocated_width()
        height = widget.get_allocated_height()
        cr.set_source_rgb(0.08, 0.08, 0.09)
        cr.paint()

        cr.set_line_width(1.0)
        cr.set_source_rgb(0.22, 0.22, 0.24)
        for step in range(5):
            x = step * width / 4
            y = step * height / 4
            cr.move_to(x, 0)
            cr.line_to(x, height)
            cr.move_to(0, y)
            cr.line_to(width, y)
            cr.stroke()

        if not self._luts:
            return False

        colors = [(1.0, 0.25, 0.25), (0.30, 1.0, 0.30), (0.35, 0.50, 1.0)]
        for color, values in zip(colors, self._luts):
            cr.set_source_rgb(*color)
            cr.set_line_width(1.6)
            for index, value in enumerate(values):
                x = index / (len(values) - 1) * width
                y = height - (value / 65535.0) * height
                if index == 0:
                    cr.move_to(x, y)
                else:
                    cr.line_to(x, y)
            cr.stroke()
        return False


class ProfileTuner(Gtk.Window):
    def __init__(self) -> None:
        super().__init__(title="Laptop Profile Tuner")
        self.set_border_width(12)
        self.set_default_size(700, 760)
        self.set_resizable(False)

        self._updating = False
        self._pending: int | None = None
        self._test_window: TestPatternWindow | None = None
        self.controls: dict[str, tuple[Gtk.Scale, Gtk.Label]] = {}

        try:
            self.baseline = xrandr_gamma.get_lut(OUTPUT)
        except Exception:
            neutral = identity_lut()
            self.baseline = (neutral, neutral[:], neutral[:])

        self._reset_ctm()

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.add(outer)

        heading = Gtk.Label()
        heading.set_markup("<b>Laptop Profile Tuner</b>")
        heading.set_xalign(0)
        outer.pack_start(heading, False, False, 0)

        subtitle = Gtk.Label(
            label=(
                "Live preview is written directly to eDP-1's gamma LUT. "
                "Save & Apply snapshots it into the ICC profile."
            )
        )
        subtitle.set_xalign(0)
        subtitle.set_line_wrap(True)
        subtitle.set_max_width_chars(78)
        outer.pack_start(subtitle, False, False, 0)

        notebook = Gtk.Notebook()
        notebook.set_size_request(-1, 370)
        outer.pack_start(notebook, False, False, 0)
        self.notebook = notebook

        basic_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        basic_box.set_border_width(10)
        basic_grid = Gtk.Grid(column_spacing=10, row_spacing=7)
        basic_box.pack_start(basic_grid, False, False, 0)
        basic_rows = [
            ("temperature", "Temperature  (− cool / + warm)", -100, 100, 0),
            ("tint", "Tint  (− green / + magenta)", -100, 100, 0),
            ("brightness", "Brightness", 0.80, 1.20, 1.00),
            ("contrast", "Contrast", 0.80, 1.20, 1.00),
            ("gamma", "Gamma", 0.70, 1.30, 1.00),
        ]
        for row, (key, label, low, high, default) in enumerate(basic_rows):
            self._add_scale(basic_grid, row, key, label, low, high, default)
        notebook.append_page(basic_box, Gtk.Label(label="Basic"))

        advanced_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        advanced_box.set_border_width(10)
        advanced_grid = Gtk.Grid(column_spacing=10, row_spacing=6)
        advanced_box.pack_start(advanced_grid, False, False, 0)
        advanced_rows = [
            ("r_gain", "Red gain", 0.80, 1.20, 1.00),
            ("g_gain", "Green gain", 0.80, 1.20, 1.00),
            ("b_gain", "Blue gain", 0.80, 1.20, 1.00),
            ("r_gamma", "Red gamma", 0.70, 1.30, 1.00),
            ("g_gamma", "Green gamma", 0.70, 1.30, 1.00),
            ("b_gamma", "Blue gamma", 0.70, 1.30, 1.00),
            ("r_black", "Red black lift", 0.00, 0.05, 0.00),
            ("g_black", "Green black lift", 0.00, 0.05, 0.00),
            ("b_black", "Blue black lift", 0.00, 0.05, 0.00),
        ]
        for row, (key, label, low, high, default) in enumerate(advanced_rows):
            self._add_scale(advanced_grid, row, key, label, low, high, default)
        notebook.append_page(advanced_box, Gtk.Label(label="Advanced"))

        frame = Gtk.Frame(label="Gamma curves")
        outer.pack_start(frame, False, False, 0)
        self.curve = CurveView()
        frame.add(self.curve)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        outer.pack_start(buttons, False, False, 0)

        reset = Gtk.Button(label="Reset")
        reset.connect("clicked", self.on_reset)
        buttons.pack_start(reset, False, False, 0)

        pattern = Gtk.Button(label="Test Pattern")
        pattern.connect("clicked", self.on_test_pattern)
        buttons.pack_start(pattern, False, False, 0)

        save = Gtk.Button(label="Save & Apply Profile")
        save.connect("clicked", self.on_save)
        buttons.pack_end(save, False, False, 0)

        self.status = Gtk.Label(label="Ready")
        self.status.set_xalign(0)
        self.status.set_line_wrap(True)
        self.status.set_max_width_chars(78)
        outer.pack_start(self.status, False, False, 0)

        self.connect("destroy", self.on_destroy)
        self.curve.set_luts(*self.baseline)
        self.schedule_apply()

    def _add_scale(
        self,
        grid: Gtk.Grid,
        row: int,
        key: str,
        label: str,
        low: float,
        high: float,
        default: float,
    ) -> None:
        label_widget = Gtk.Label(label=label)
        label_widget.set_xalign(0)
        grid.attach(label_widget, 0, row, 1, 1)

        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, low, high, 0.01)
        scale.set_value(default)
        scale.set_digits(2)
        scale.set_hexpand(True)
        scale.set_size_request(360, -1)
        scale.connect("value-changed", self.on_scale_changed)
        grid.attach(scale, 1, row, 1, 1)

        value_label = Gtk.Label(label=f"{default:.2f}")
        value_label.set_width_chars(5)
        value_label.set_xalign(1)
        grid.attach(value_label, 2, row, 1, 1)
        self.controls[key] = (scale, value_label)

    def _reset_ctm(self) -> None:
        try:
            subprocess.run(
                ["xrandr", "--output", OUTPUT, "--set", "CTM", IDENTITY_CTM],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
        except (OSError, subprocess.CalledProcessError):
            pass

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

    def compute_luts(self) -> tuple[list[int], list[int], list[int]]:
        values = self.read_values()
        temperature = values["temperature"] / 100.0
        tint = values["tint"] / 100.0

        red_gain = values["r_gain"] * values["brightness"] * (1.0 + 0.15 * temperature)
        green_gain = values["g_gain"] * values["brightness"] * (1.0 - 0.10 * tint)
        blue_gain = values["b_gain"] * values["brightness"] * (1.0 - 0.15 * temperature)

        red_gamma = max(0.2, values["gamma"] * values["r_gamma"])
        green_gamma = max(0.2, values["gamma"] * values["g_gamma"])
        blue_gamma = max(0.2, values["gamma"] * values["b_gamma"])

        contrast = values["contrast"]
        return (
            channel_lut(
                self.baseline[0],
                red_gain,
                red_gamma,
                contrast,
                values["r_black"],
            ),
            channel_lut(
                self.baseline[1],
                green_gain,
                green_gamma,
                contrast,
                values["g_black"],
            ),
            channel_lut(
                self.baseline[2],
                blue_gain,
                blue_gamma,
                contrast,
                values["b_black"],
            ),
        )

    def apply_current(self) -> bool:
        self._pending = None
        luts = self.compute_luts()
        try:
            xrandr_gamma.set_lut(OUTPUT, *luts)
        except Exception as exc:
            self.set_status(f"ERROR: {exc}")
            return False
        self.curve.set_luts(*luts)
        self.set_status("Live preview applied to eDP-1")
        return False

    def on_reset(self, _button: Gtk.Button) -> None:
        self._updating = True
        for key, (scale, value_label) in self.controls.items():
            default = 0.0 if key in {"temperature", "tint"} else 1.0
            if key.endswith("_black"):
                default = 0.0
            scale.set_value(default)
            value_label.set_text(f"{default:.2f}")
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
        luts = self.compute_luts()
        try:
            with open(make_profile.SOURCE_PROFILE, "rb") as handle:
                source = handle.read()
            profile = make_profile.build_profile_from_luts(source, *luts)
            os.makedirs(os.path.dirname(PROFILE_PATH), exist_ok=True)
            with open(PROFILE_PATH, "wb") as handle:
                handle.write(profile)
            profile_install.install_profile(PROFILE_PATH, OUTPUT)
            xrandr_gamma.set_lut(OUTPUT, *luts)
        except Exception as exc:
            self.set_status(f"ERROR: {exc}")
            return
        self.baseline = luts
        self.set_status(f"Saved and applied profile: {PROFILE_PATH}")

    def on_destroy(self, _widget: Gtk.Widget) -> None:
        if self._pending is not None:
            GLib.source_remove(self._pending)
            self._pending = None
        try:
            xrandr_gamma.set_lut(OUTPUT, *self.baseline)
        except Exception:
            pass
        Gtk.main_quit()

    def place_main_window(self) -> bool:
        x, y, width, height = get_output_geometry()
        win_width, win_height = self.get_size()
        self.move(
            x + max(20, (width - win_width) // 2),
            y + max(20, (height - win_height) // 2),
        )
        return False


def main() -> int:
    window = ProfileTuner()
    window.show_all()
    GLib.timeout_add(150, window.place_main_window)
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())

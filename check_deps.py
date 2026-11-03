#!/usr/bin/python3
"""Check whether this machine has what the Profile Tuner needs."""

from __future__ import annotations

import ctypes.util
import os
import shutil
import subprocess
import sys

MIN_PYTHON = (3, 10)
PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"


def _check_python() -> tuple[str, str]:
    if sys.version_info >= MIN_PYTHON:
        return PASS, f"Python {sys.version.split()[0]}"
    return FAIL, f"Python {sys.version.split()[0]} (need 3.10+)"


def _check_x11() -> tuple[str, str]:
    session = os.environ.get("XDG_SESSION_TYPE", "unknown")
    display = os.environ.get("DISPLAY")
    if session == "x11" and display:
        return PASS, f"X11 session, DISPLAY={display}"
    if session == "wayland":
        return FAIL, "Wayland session — log into an X11/Xorg session"
    if not display:
        return FAIL, "DISPLAY is not set — run from a graphical session"
    return WARN, f"session={session}, DISPLAY={display}"


def _check_command(name: str, label: str | None = None) -> tuple[str, str]:
    path = shutil.which(name)
    if path:
        return PASS, f"{label or name}: {path}"
    return FAIL, f"{label or name}: not found in PATH"


def _check_libs() -> list[tuple[str, str]]:
    results = []
    for library, label in (("X11", "libX11"), ("Xrandr", "libXrandr")):
        path = ctypes.util.find_library(library)
        if path:
            results.append((PASS, f"{label}: {path}"))
        else:
            results.append((FAIL, f"{label}: not found"))
    return results


def _check_gtk() -> tuple[str, str]:
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk  # noqa: F401
    except Exception as exc:
        return FAIL, f"PyGObject/GTK3 unavailable: {exc}"
    return PASS, "PyGObject + GTK3 available"


def _check_colord() -> tuple[str, str]:
    if not shutil.which("colormgr"):
        return FAIL, "colormgr not found — install colord"
    try:
        result = subprocess.run(
            ["colormgr", "get-devices"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except OSError as exc:
        return FAIL, f"colormgr could not run: {exc}"
    if result.returncode != 0:
        return FAIL, f"colormgr failed: {(result.stderr or result.stdout).strip()}"
    if "XRANDR_name=" not in result.stdout:
        return FAIL, "colord is running but reports no XRandR display devices"
    return PASS, "colord reports display devices"


def _check_color_manager() -> tuple[str, str]:
    managers = ("csd-color", "gsd-color", "colord-kde", "colord-kde-daemon")
    running = []
    try:
        output = subprocess.check_output(
            ["ps", "-eo", "comm="],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        names = {line.strip() for line in output.splitlines()}
        running = [name for name in managers if name in names]
    except (OSError, subprocess.CalledProcessError):
        pass
    if running:
        return PASS, f"desktop colour manager: {', '.join(running)}"
    return WARN, (
        "no known desktop colour manager found (csd-color, gsd-color, "
        "colord-kde) — live preview may work, but login persistence may not"
    )


def main() -> int:
    checks: list[tuple[str, str]] = []
    checks.append(_check_python())
    checks.append(_check_x11())
    checks.append(_check_command("xrandr"))
    checks.extend(_check_libs())
    checks.append(_check_gtk())
    checks.append(_check_colord())
    checks.append(_check_color_manager())

    print("Manual Calibration Tools — dependency check\n")
    failures = 0
    for status, message in checks:
        if status == FAIL:
            failures += 1
        print(f"[{status}] {message}")

    print()
    if failures:
        print(f"Result: {failures} required check(s) failed. See README.md → Install.")
        return 1
    print("Result: ready. Run: python3 profile_tuner.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())

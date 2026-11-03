#!/usr/bin/python3
"""Discover connected XRandR outputs and choose a calibration target."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass

_OUTPUT_RE = re.compile(
    r"^(\S+) connected( primary)? (\d+)x(\d+)\+(\d+)\+(\d+)",
    re.MULTILINE,
)
_INTERNAL_RE = re.compile(r"^(eDP|LVDS|DSI|DPI)-", re.IGNORECASE)


@dataclass(frozen=True)
class Monitor:
    name: str
    width: int
    height: int
    x: int
    y: int
    primary: bool
    internal: bool

    def label(self) -> str:
        tags = []
        if self.internal:
            tags.append("internal")
        if self.primary:
            tags.append("primary")
        suffix = f" — {', '.join(tags)}" if tags else ""
        return f"{self.name}  {self.width}×{self.height}{suffix}"


def parse_monitors(query_output: str) -> list[Monitor]:
    monitors: list[Monitor] = []
    for match in _OUTPUT_RE.finditer(query_output):
        name, primary, width, height, x, y = match.groups()
        monitors.append(
            Monitor(
                name=name,
                width=int(width),
                height=int(height),
                x=int(x),
                y=int(y),
                primary=bool(primary),
                internal=bool(_INTERNAL_RE.match(name)),
            )
        )
    return monitors


def list_monitors() -> list[Monitor]:
    try:
        output = subprocess.check_output(
            ["xrandr", "--query"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    return parse_monitors(output)


def default_output(monitors: list[Monitor] | None = None) -> str | None:
    monitors = list_monitors() if monitors is None else monitors
    for monitor in monitors:
        if monitor.internal:
            return monitor.name
    for monitor in monitors:
        if monitor.primary:
            return monitor.name
    return monitors[0].name if monitors else None


def resolve_output(requested: str | None = None) -> str:
    monitors = list_monitors()
    names = {monitor.name for monitor in monitors}
    if requested:
        if requested not in names:
            available = ", ".join(sorted(names)) or "none"
            raise ValueError(
                f"output {requested!r} is not connected (available: {available})"
            )
        return requested
    chosen = default_output(monitors)
    if not chosen:
        raise RuntimeError("no connected XRandR output found")
    return chosen

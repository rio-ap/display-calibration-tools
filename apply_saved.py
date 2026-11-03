#!/usr/bin/python3
"""Reapply the saved laptop colour matrix at login.

Reads ~/.config/laptop-color-tuner/last.json and applies its CTM values to
eDP-1. Retries briefly because Cinnamon may still be setting up outputs when
autostart runs.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time

DEFAULT_OUTPUT = "eDP-1"
CONFIG_PATH = os.path.expanduser("~/.config/laptop-color-tuner/last.json")
LOG_PATH = os.path.expanduser("~/.config/laptop-color-tuner/apply.log")


def log(message: str) -> None:
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as handle:
            handle.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")
    except OSError:
        pass


def load_reference() -> tuple[str, str] | None:
    if not os.path.exists(CONFIG_PATH):
        log("no saved reference; nothing to apply")
        return None
    try:
        with open(CONFIG_PATH, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        log(f"could not read reference: {exc}")
        return None

    output = str(data.get("output", DEFAULT_OUTPUT))
    ctm = data.get("ctm")
    if not isinstance(ctm, list) or len(ctm) != 18:
        log("saved reference has an invalid CTM")
        return None
    try:
        value = ",".join(str(int(item)) for item in ctm)
    except (TypeError, ValueError) as exc:
        log(f"saved reference has a non-numeric CTM: {exc}")
        return None
    return output, value


def apply_reference(output: str, value: str) -> bool:
    connected = re.compile(rf"^{re.escape(output)} connected", re.MULTILINE)
    for attempt in range(20):
        try:
            query = subprocess.run(
                ["xrandr", "--query"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if query.returncode == 0 and connected.search(query.stdout):
                result = subprocess.run(
                    ["xrandr", "--output", output, "--set", "CTM", value],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                if result.returncode == 0:
                    log(f"applied saved reference to {output}")
                    return True
                log(f"apply failed: {(result.stderr or result.stdout).strip()}")
        except OSError as exc:
            log(f"attempt {attempt + 1}: {exc}")
        time.sleep(0.5)
    log("gave up waiting for the output")
    return False


def main() -> int:
    reference = load_reference()
    if reference is None:
        return 1
    output, value = reference
    return 0 if apply_reference(output, value) else 1


if __name__ == "__main__":
    sys.exit(main())

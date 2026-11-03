#!/usr/bin/python3
"""Install and assign a generated display profile through colord."""

from __future__ import annotations

import re
import subprocess


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _object_path(text: str) -> str | None:
    match = re.search(r"^Object Path:\s+(\S+)", text, re.MULTILINE)
    return match.group(1) if match else None


def find_device_path(output: str) -> str:
    result = _run(["colormgr", "get-devices"])
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip())
    for block in result.stdout.split("\n\n"):
        if f"XRANDR_name={output}" in block:
            path = _object_path(block)
            if path:
                return path
    raise RuntimeError(f"colord device for {output!r} not found")


def find_profile_by_filename(path: str) -> tuple[str, str] | None:
    result = _run(["colormgr", "find-profile-by-filename", path])
    if result.returncode != 0:
        return None
    object_path = _object_path(result.stdout)
    match = re.search(r"^Profile ID:\s+(\S+)", result.stdout, re.MULTILINE)
    if not object_path or not match:
        return None
    return object_path, match.group(1)


def delete_profile_by_filename(path: str) -> None:
    found = find_profile_by_filename(path)
    if not found:
        return
    _, profile_id = found
    result = _run(["colormgr", "delete-profile", profile_id])
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip())


def install_profile(path: str, output: str) -> str:
    """Replace the profile at *path*, import it, and assign it to *output*."""
    delete_profile_by_filename(path)

    result = _run(["colormgr", "import-profile", path])
    imported_path = _object_path(result.stdout)
    if result.returncode != 0 and "already exists" not in (
        result.stderr + result.stdout
    ):
        raise RuntimeError((result.stderr or result.stdout).strip())

    found = find_profile_by_filename(path)
    if found:
        profile_path = found[0]
    elif imported_path:
        profile_path = imported_path
    else:
        raise RuntimeError("colord imported the profile but did not return its path")

    device_path = find_device_path(output)
    add = _run(["colormgr", "device-add-profile", device_path, profile_path])
    if add.returncode != 0:
        raise RuntimeError((add.stderr or add.stdout).strip())

    make_default = _run(
        ["colormgr", "device-make-profile-default", device_path, profile_path]
    )
    if make_default.returncode != 0:
        raise RuntimeError((make_default.stderr or make_default.stdout).strip())

    return profile_path

#!/usr/bin/python3
"""Build a synthetic display ICC profile with a VCGT calibration table.

This is not a colorimeter measurement. It takes the saved per-channel gains
from the tuner and writes them into the profile's Video Card Gamma Table so
colord/csd-color can apply them at login.
"""

from __future__ import annotations

import hashlib
import json
import os
import struct
import sys

SOURCE_PROFILE = os.path.expanduser(
    "~/.local/share/icc/edid-1eec840f5baccc8e533ba13fc2fb3e33.icc"
)
SAVED_REFERENCE = os.path.expanduser("~/.config/laptop-color-tuner/last.json")
OUTPUT_PROFILE = os.path.expanduser("~/.local/share/icc/laptop-color-reference.icc")

VCGT_ENTRIES = 256


def make_vcgt(red: float, green: float, blue: float) -> bytes:
    """Create an Apple/ICC vcgt table with per-channel linear gain curves."""
    header = (
        b"vcgt"
        + b"\x00" * 4
        + struct.pack(">I", 0)  # table type
        + struct.pack(">HHH", 3, VCGT_ENTRIES, 2)  # channels, entries, entry size
    )
    body = bytearray()
    for gain in (red, green, blue):
        for index in range(VCGT_ENTRIES):
            value = int(round(gain * (index / (VCGT_ENTRIES - 1)) * 65535))
            value = max(0, min(65535, value))
            body.extend(struct.pack(">H", value))
    return header + bytes(body)


def parse_tags(data: bytes) -> list[tuple[bytes, bytes]]:
    tag_count = struct.unpack(">I", data[128:132])[0]
    tags: list[tuple[bytes, bytes]] = []
    for index in range(tag_count):
        entry = 132 + index * 12
        signature = data[entry : entry + 4]
        offset, size = struct.unpack(">II", data[entry + 4 : entry + 12])
        tags.append((signature, data[offset : offset + size]))
    return tags


def rebuild_profile(source: bytes, tags: list[tuple[bytes, bytes]]) -> bytes:
    count = len(tags)
    tag_table = bytearray(struct.pack(">I", count))
    base_offset = 128 + len(tag_table) + 12 * count
    payload = bytearray()
    entries: list[tuple[bytes, int, int]] = []

    for signature, tag_data in tags:
        offset = base_offset + len(payload)
        padding = (-offset) % 4
        if padding:
            payload.extend(b"\x00" * padding)
            offset += padding
        entries.append((signature, offset, len(tag_data)))
        payload.extend(tag_data)

    for signature, offset, size in entries:
        tag_table.extend(signature)
        tag_table.extend(struct.pack(">II", offset, size))

    header = bytearray(source[:128])
    total_size = 128 + len(tag_table) + len(payload)
    header[0:4] = struct.pack(">I", total_size)
    header[84:100] = b"\x00" * 16  # profile ID is recomputed below

    profile = header + tag_table + payload
    digest = hashlib.md5(profile).digest()
    profile[84:100] = digest
    return bytes(profile)


def build_profile(source: bytes, red: float, green: float, blue: float) -> bytes:
    tags = [(sig, data) for sig, data in parse_tags(source) if sig != b"vcgt"]
    tags.append((b"vcgt", make_vcgt(red, green, blue)))
    return rebuild_profile(source, tags)


def load_saved_gains(path: str = SAVED_REFERENCE) -> tuple[float, float, float]:
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    saturation = float(data.get("saturation", 1.0))
    if abs(saturation - 1.0) > 0.001:
        raise ValueError(
            "This profile builder only represents per-channel gains; "
            f"saved saturation is {saturation:.2f}, not 1.00."
        )
    gains = data["gains"]
    return float(gains["red"]), float(gains["green"]), float(gains["blue"])


def main() -> int:
    try:
        red, green, blue = load_saved_gains()
        with open(SOURCE_PROFILE, "rb") as handle:
            source = handle.read()
        profile = build_profile(source, red, green, blue)
        os.makedirs(os.path.dirname(OUTPUT_PROFILE), exist_ok=True)
        with open(OUTPUT_PROFILE, "wb") as handle:
            handle.write(profile)
    except (OSError, ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(OUTPUT_PROFILE)
    print(f"gains: R={red:.2f} G={green:.2f} B={blue:.2f}")
    print(f"size: {len(profile)} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())

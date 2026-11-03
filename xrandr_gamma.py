#!/usr/bin/python3
"""Read and write per-output XRandR gamma LUTs with ctypes."""

from __future__ import annotations

import ctypes
from ctypes import POINTER, Structure, c_char_p, c_int, c_ulong, c_ushort, c_void_p

class XRRScreenResources(Structure):
    _fields_ = [
        ("timestamp", c_ulong),
        ("configTimestamp", c_ulong),
        ("ncrtc", c_int),
        ("crtcs", POINTER(c_ulong)),
        ("noutput", c_int),
        ("outputs", POINTER(c_ulong)),
        ("nmode", c_int),
        ("modes", c_void_p),
    ]


class XRROutputInfo(Structure):
    _fields_ = [
        ("timestamp", c_ulong),
        ("crtc", c_ulong),
        ("name", c_char_p),
        ("nameLen", c_int),
        ("mm_width", c_ulong),
        ("mm_height", c_ulong),
        ("connection", c_int),
        ("subpixel_order", c_int),
        ("ncrtc", c_int),
        ("crtcs", POINTER(c_ulong)),
        ("nclone", c_int),
        ("clones", POINTER(c_ulong)),
        ("nmode", c_int),
        ("npreferred", c_int),
        ("modes", POINTER(c_ulong)),
    ]


class XRRCrtcGamma(Structure):
    _fields_ = [
        ("size", c_int),
        ("red", POINTER(c_ushort)),
        ("green", POINTER(c_ushort)),
        ("blue", POINTER(c_ushort)),
    ]


def _load_libraries() -> tuple[ctypes.CDLL, ctypes.CDLL]:
    x11 = ctypes.CDLL("libX11.so.6")
    xrandr = ctypes.CDLL("libXrandr.so.2")

    x11.XOpenDisplay.restype = c_void_p
    x11.XOpenDisplay.argtypes = [c_char_p]
    x11.XCloseDisplay.argtypes = [c_void_p]
    x11.XDefaultRootWindow.restype = c_ulong
    x11.XDefaultRootWindow.argtypes = [c_void_p]

    xrandr.XRRGetScreenResourcesCurrent.restype = POINTER(XRRScreenResources)
    xrandr.XRRGetScreenResourcesCurrent.argtypes = [c_void_p, c_ulong]
    xrandr.XRRFreeScreenResources.argtypes = [POINTER(XRRScreenResources)]
    xrandr.XRRGetOutputInfo.restype = POINTER(XRROutputInfo)
    xrandr.XRRGetOutputInfo.argtypes = [
        c_void_p,
        POINTER(XRRScreenResources),
        c_ulong,
    ]
    xrandr.XRRFreeOutputInfo.argtypes = [POINTER(XRROutputInfo)]
    xrandr.XRRGetCrtcGammaSize.restype = c_int
    xrandr.XRRGetCrtcGammaSize.argtypes = [c_void_p, c_ulong]
    xrandr.XRRGetCrtcGamma.restype = POINTER(XRRCrtcGamma)
    xrandr.XRRGetCrtcGamma.argtypes = [c_void_p, c_ulong]
    xrandr.XRRAllocGamma.restype = POINTER(XRRCrtcGamma)
    xrandr.XRRAllocGamma.argtypes = [c_int]
    xrandr.XRRSetCrtcGamma.argtypes = [c_void_p, c_ulong, POINTER(XRRCrtcGamma)]
    xrandr.XRRFreeGamma.argtypes = [POINTER(XRRCrtcGamma)]
    return x11, xrandr


def _with_crtc(output: str):
    x11, xrandr = _load_libraries()
    display = x11.XOpenDisplay(None)
    if not display:
        raise RuntimeError("cannot open X display")
    resources = xrandr.XRRGetScreenResourcesCurrent(
        display, x11.XDefaultRootWindow(display)
    )
    if not resources:
        x11.XCloseDisplay(display)
        raise RuntimeError("cannot read XRandR screen resources")
    try:
        for index in range(resources.contents.noutput):
            output_id = resources.contents.outputs[index]
            info = xrandr.XRRGetOutputInfo(display, resources, output_id)
            if not info:
                continue
            try:
                name = info.contents.name[: info.contents.nameLen].decode()
                if name == output:
                    return x11, xrandr, display, info.contents.crtc, resources
            finally:
                xrandr.XRRFreeOutputInfo(info)
        raise RuntimeError(f"output {output!r} not found")
    except Exception:
        xrandr.XRRFreeScreenResources(resources)
        x11.XCloseDisplay(display)
        raise


def _close(x11, xrandr, display, resources) -> None:
    xrandr.XRRFreeScreenResources(resources)
    x11.XCloseDisplay(display)


def resample(values: list[int], size: int) -> list[int]:
    if len(values) == size:
        return [int(value) for value in values]
    if not values:
        raise ValueError("empty LUT")
    result: list[int] = []
    last = len(values) - 1
    for index in range(size):
        position = index * last / (size - 1)
        low = int(position)
        high = min(low + 1, last)
        fraction = position - low
        value = values[low] * (1.0 - fraction) + values[high] * fraction
        result.append(max(0, min(65535, int(round(value)))))
    return result


def get_lut(output: str) -> tuple[list[int], list[int], list[int]]:
    x11, xrandr, display, crtc, resources = _with_crtc(output)
    try:
        size = xrandr.XRRGetCrtcGammaSize(display, crtc)
        if size <= 0:
            raise RuntimeError("display reports no gamma table")
        gamma = xrandr.XRRGetCrtcGamma(display, crtc)
        if not gamma:
            raise RuntimeError("cannot read gamma table")
        try:
            return (
                [int(gamma.contents.red[i]) for i in range(size)],
                [int(gamma.contents.green[i]) for i in range(size)],
                [int(gamma.contents.blue[i]) for i in range(size)],
            )
        finally:
            xrandr.XRRFreeGamma(gamma)
    finally:
        _close(x11, xrandr, display, resources)


def set_lut(
    output: str,
    red: list[int],
    green: list[int],
    blue: list[int],
) -> None:
    x11, xrandr, display, crtc, resources = _with_crtc(output)
    try:
        size = xrandr.XRRGetCrtcGammaSize(display, crtc)
        if size <= 0:
            raise RuntimeError("display reports no gamma table")
        red_values = resample(red, size)
        green_values = resample(green, size)
        blue_values = resample(blue, size)
        gamma = xrandr.XRRAllocGamma(size)
        if not gamma:
            raise RuntimeError("cannot allocate gamma table")
        try:
            for index in range(size):
                gamma.contents.red[index] = red_values[index]
                gamma.contents.green[index] = green_values[index]
                gamma.contents.blue[index] = blue_values[index]
            xrandr.XRRSetCrtcGamma(display, crtc, gamma)
        finally:
            xrandr.XRRFreeGamma(gamma)
    finally:
        _close(x11, xrandr, display, resources)

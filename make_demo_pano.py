#!/usr/bin/env python3
"""Generate images/demo-pano.png — a synthetic equirectangular test panorama.

pano.html needs *something* to show before a real 360 photo exists. This
renders a 2:1 equirectangular image procedurally (sky gradient, sun, ground
checkerboard, four colored cardinal markers) so it is obvious at a glance
which way you are looking and that dragging works.

    ./make_demo_pano.py            # writes images/demo-pano.png

Only needs numpy — PNG encoding is done here with zlib to avoid a Pillow
dependency. Replace the image with a real equirectangular photo whenever you
have one; nothing else depends on this script.
"""

import struct
import sys
import zlib

import numpy as np

W, H = 2048, 1024
OUT = "images/demo-pano.png"

# Cardinal markers: (longitude degrees, RGB)
MARKERS = [
    (0.0,   (232,  74,  74)),   # north  — red
    (90.0,  (240, 190,  70)),   # east   — amber
    (180.0, (110, 200, 130)),   # south  — green
    (270.0, (100, 150, 235)),   # west   — blue
]


def render() -> np.ndarray:
    # Equirectangular parameterisation: u spans longitude, v spans latitude.
    u = (np.arange(W) + 0.5) / W
    v = (np.arange(H) + 0.5) / H
    lon = (u * 2.0 - 1.0) * np.pi          # -pi .. pi
    lat = (0.5 - v) * np.pi                # +pi/2 (up) .. -pi/2 (down)
    lon, lat = np.meshgrid(lon, lat)

    cl = np.cos(lat)
    dx = cl * np.sin(lon)
    dy = np.sin(lat)
    dz = -cl * np.cos(lon)

    img = np.zeros((H, W, 3), np.float64)

    # --- sky -------------------------------------------------------------
    up = np.clip(dy, 0.0, 1.0)
    horizon = np.array([252.0, 236.0, 214.0])
    zenith = np.array([54.0, 108.0, 196.0])
    sky = horizon + (zenith - horizon) * (up ** 0.55)[..., None]

    # soft banded clouds, thinned out near the zenith
    band = np.sin(lon * 3.0 + np.sin(lat * 7.0) * 1.6) * np.sin(lat * 11.0)
    cloud = np.clip(band * 0.5 + 0.15, 0.0, 1.0) * np.clip(1.0 - up * 1.4, 0.0, 1.0)
    sky += (np.array([255.0, 255.0, 255.0]) - sky) * (cloud * 0.55)[..., None]

    # sun: a bright core with a wide falloff halo
    sun_lon, sun_lat = np.radians(40.0), np.radians(24.0)
    sx = np.cos(sun_lat) * np.sin(sun_lon)
    sy = np.sin(sun_lat)
    sz = -np.cos(sun_lat) * np.cos(sun_lon)
    cos_sun = np.clip(dx * sx + dy * sy + dz * sz, 0.0, 1.0)
    sun = cos_sun ** 900.0 + (cos_sun ** 24.0) * 0.35
    sky += np.array([255.0, 244.0, 214.0]) * np.clip(sun, 0.0, 1.0)[..., None]

    # --- ground ----------------------------------------------------------
    # Project each downward ray onto a plane 1.6 units below the viewer.
    down = np.minimum(dy, -1e-4)
    t = -1.6 / down
    px, pz = dx * t, dz * t
    checker = (np.floor(px) + np.floor(pz)) % 2.0
    ground = np.where(checker[..., None] > 0.5,
                      np.array([62.0, 66.0, 72.0]),
                      np.array([92.0, 98.0, 106.0]))

    # metre-ish grid lines on top of the checker
    line = np.minimum(np.abs(px - np.round(px)), np.abs(pz - np.round(pz)))
    ground += (np.array([190.0, 200.0, 210.0]) - ground) * \
        np.clip(1.0 - line * 24.0, 0.0, 1.0)[..., None] * 0.6

    # distance haze so the ground melts into the horizon
    dist = np.sqrt(px * px + pz * pz)
    haze = np.clip(dist / 26.0, 0.0, 1.0)[..., None]
    ground = ground + (horizon - ground) * haze

    img = np.where((dy > 0.0)[..., None], sky, ground)

    # --- cardinal markers ------------------------------------------------
    lon_deg = np.degrees(lon) % 360.0
    lat_deg = np.degrees(lat)
    for m_lon, color in MARKERS:
        delta = np.abs((lon_deg - m_lon + 180.0) % 360.0 - 180.0)
        post = (delta < 2.6) & (lat_deg > -9.0) & (lat_deg < 21.0)
        # rungs up the post give an unambiguous sense of vertical motion
        rung = post & (np.sin(np.radians(lat_deg) * 40.0) > 0.55)
        img[post] = color
        img[rung] = np.array(color) * 0.45 + 255.0 * 0.15

    return np.clip(img, 0.0, 255.0).astype(np.uint8)


def write_png(path: str, rgb: np.ndarray) -> None:
    h, w, _ = rgb.shape
    # Per-row "sub" filter: neighbouring pixels are near-identical in the sky
    # and ground gradients, so this compresses far better than no filter.
    sub = rgb.astype(np.int16)
    sub[:, 1:] -= rgb[:, :-1].astype(np.int16)
    rows = np.empty((h, 1 + w * 3), np.uint8)
    rows[:, 0] = 1                                    # filter type: sub
    rows[:, 1:] = sub.astype(np.uint8).reshape(h, -1)
    raw = rows.tobytes()

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data +
                struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 9))
           + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)


def main() -> int:
    out = sys.argv[1] if len(sys.argv) > 1 else OUT
    write_png(out, render())
    print(f"wrote {out} ({W}x{H})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

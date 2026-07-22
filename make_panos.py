#!/usr/bin/env python3
"""Generate the placeholder panoramas in images/.

These are procedural stand-ins so the rooms have something to show until real
equirectangular art exists. Each renders a full sphere: for every pixel we turn
(x, y) into a direction vector and decide what colour is out that way.

    ./make_panos.py            # writes every scene
    ./make_panos.py void       # writes just images/pano-void.png

Only needs numpy — PNG encoding is done here with zlib to avoid a Pillow
dependency. Add a room by writing a render function and listing it in SCENES.
"""

import struct
import sys
import zlib

import numpy as np

W, H = 2048, 1024
GROUND = -1.6          # eye height above the floor plane, in metres-ish


def directions():
    """Per-pixel (longitude, latitude) and the unit vector pointing that way."""
    u = (np.arange(W) + 0.5) / W
    v = (np.arange(H) + 0.5) / H
    lon = (u * 2.0 - 1.0) * np.pi          # -pi .. pi
    lat = (0.5 - v) * np.pi                # +pi/2 (up) .. -pi/2 (down)
    lon, lat = np.meshgrid(lon, lat)
    cl = np.cos(lat)
    return lon, lat, cl * np.sin(lon), np.sin(lat), -cl * np.cos(lon)


def floor_plane(dx, dy, dz):
    """Project downward rays onto the floor. Returns (x, z, distance)."""
    t = GROUND / np.minimum(dy, -1e-4)
    px, pz = dx * t, dz * t
    return px, pz, np.sqrt(px * px + pz * pz)


def angular_dist(lon, lat, t_lon, t_lat):
    """Great-circle angle from every pixel to a target direction, in radians."""
    tx = np.cos(t_lat) * np.sin(t_lon)
    ty = np.sin(t_lat)
    tz = -np.cos(t_lat) * np.cos(t_lon)
    cl = np.cos(lat)
    dot = cl * np.sin(lon) * tx + np.sin(lat) * ty + (-cl * np.cos(lon)) * tz
    return np.arccos(np.clip(dot, -1.0, 1.0))


# ---------------------------------------------------------------------------
# Rooms
# ---------------------------------------------------------------------------

def hub():
    """Open daylight plain. The calibration space: coloured posts at N/E/S/W."""
    lon, lat, dx, dy, dz = directions()
    horizon = np.array([252.0, 236.0, 214.0])
    zenith = np.array([54.0, 108.0, 196.0])

    up = np.clip(dy, 0.0, 1.0)
    sky = horizon + (zenith - horizon) * (up ** 0.55)[..., None]

    band = np.sin(lon * 3.0 + np.sin(lat * 7.0) * 1.6) * np.sin(lat * 11.0)
    cloud = np.clip(band * 0.5 + 0.15, 0.0, 1.0) * np.clip(1.0 - up * 1.4, 0.0, 1.0)
    sky += (255.0 - sky) * (cloud * 0.55)[..., None]

    sun = angular_dist(lon, lat, np.radians(40.0), np.radians(24.0))
    glow = np.exp(-(sun / 0.035) ** 2) + np.exp(-(sun / 0.30) ** 2) * 0.35
    sky += np.array([255.0, 244.0, 214.0]) * np.clip(glow, 0.0, 1.0)[..., None]

    px, pz, dist = floor_plane(dx, dy, dz)
    checker = (np.floor(px) + np.floor(pz)) % 2.0
    ground = np.where(checker[..., None] > 0.5,
                      np.array([62.0, 66.0, 72.0]), np.array([92.0, 98.0, 106.0]))
    line = np.minimum(np.abs(px - np.round(px)), np.abs(pz - np.round(pz)))
    ground += (np.array([190.0, 200.0, 210.0]) - ground) * \
        np.clip(1.0 - line * 24.0, 0.0, 1.0)[..., None] * 0.6
    ground += (horizon - ground) * np.clip(dist / 26.0, 0.0, 1.0)[..., None]

    img = np.where((dy > 0.0)[..., None], sky, ground)

    # Cardinal posts, so orientation stays unambiguous while testing.
    lon_deg, lat_deg = np.degrees(lon) % 360.0, np.degrees(lat)
    for m_lon, color in [(0.0, (232, 74, 74)), (90.0, (240, 190, 70)),
                         (180.0, (110, 200, 130)), (270.0, (100, 150, 235))]:
        delta = np.abs((lon_deg - m_lon + 180.0) % 360.0 - 180.0)
        post = (delta < 2.6) & (lat_deg > -9.0) & (lat_deg < 21.0)
        img[post] = color
        img[post & (np.sin(np.radians(lat_deg) * 40.0) > 0.55)] = \
            np.array(color) * 0.45 + 255.0 * 0.15

    return img


def void():
    """Deep space: starfield, nebula haze, a cold moon, a barely-there floor."""
    rng = np.random.default_rng(7)
    lon, lat, dx, dy, dz = directions()

    up = np.clip(dy, 0.0, 1.0)
    img = np.array([7.0, 8.0, 16.0]) + np.array([10.0, 6.0, 22.0]) * (1.0 - up)[..., None]

    # Nebula: a few octaves of cheap sine noise, squared into drifting patches.
    n = np.zeros_like(lat)
    for freq, amp in [(1.7, 1.0), (3.9, 0.5), (8.3, 0.25)]:
        n += amp * np.sin(lon * freq + np.sin(lat * freq * 0.7) * 2.2) \
                 * np.cos(lat * freq * 1.3 + np.sin(lon * freq) * 1.1)
    n = np.clip(n * 0.4 + 0.35, 0.0, 1.0) ** 2.0
    img += np.array([70.0, 30.0, 110.0]) * n[..., None] * 0.55
    img += np.array([0.0, 60.0, 90.0]) * \
        (n * np.clip(np.sin(lon * 2.0 + 1.0), 0.0, 1.0))[..., None] * 0.3

    # Stars, spread evenly over the sphere (uniform in sin(latitude), not in
    # latitude — otherwise they bunch up at the poles).
    count = 2600
    s_lat = np.arcsin(rng.uniform(-1.0, 1.0, count))
    s_lon = rng.uniform(-np.pi, np.pi, count)
    sx = ((s_lon / (2 * np.pi) + 0.5) * W).astype(int) % W
    sy = np.clip(((0.5 - s_lat / np.pi) * H).astype(int), 0, H - 1)
    mag = rng.power(0.35, count) * 255.0
    tint = 0.75 + rng.uniform(0.0, 0.25, count)[:, None] * np.array([[1.0, 0.95, 0.8]])
    np.maximum.at(img, (sy, sx), mag[:, None] * tint)

    # The brightest handful get a soft bloom.
    for i in np.argsort(mag)[-14:]:
        d = angular_dist(lon, lat, s_lon[i], s_lat[i])
        img += np.array([190.0, 205.0, 255.0]) * np.exp(-(d / 0.012) ** 2)[..., None]

    # A cold moon, low in the west.
    d = angular_dist(lon, lat, np.radians(255.0), np.radians(12.0))
    disc = np.clip((0.115 - d) / 0.006, 0.0, 1.0)
    limb = 0.55 + 0.45 * np.clip(1.0 - d / 0.115, 0.0, 1.0) ** 0.4
    img = img * (1.0 - disc[..., None]) + \
        (np.array([206.0, 214.0, 232.0]) * limb[..., None]) * disc[..., None]
    img += np.array([120.0, 140.0, 190.0]) * np.exp(-(d / 0.20) ** 2)[..., None] * 0.5

    # Floor: concentric rings fading out, just enough to stand on.
    px, pz, dist = floor_plane(dx, dy, dz)
    ring = np.abs(np.sin(dist * 1.6)) ** 26.0
    fade = np.clip(1.0 - dist / 30.0, 0.0, 1.0)
    ground = np.array([6.0, 7.0, 13.0]) + \
        np.array([40.0, 90.0, 120.0]) * (ring * fade)[..., None]
    img = np.where((dy > 0.0)[..., None], img, ground)

    return img


def hall():
    """Interior: a ring of monoliths with gaps at the exits, warm fog, dark ceiling."""
    lon, lat, dx, dy, dz = directions()
    lon_deg, lat_deg = np.degrees(lon) % 360.0, np.degrees(lat)

    up = np.clip(dy, 0.0, 1.0)
    img = np.array([46.0, 38.0, 34.0]) + \
        np.array([-38.0, -30.0, -26.0]) * (up ** 0.5)[..., None]

    # A dim light directly overhead.
    img += np.array([120.0, 96.0, 70.0]) * \
        np.exp(-((np.pi / 2 - lat) / 0.55) ** 2)[..., None] * 0.5

    # Warm haze gathered at eye level.
    img += np.array([120.0, 84.0, 56.0]) * np.exp(-(lat / 0.16) ** 2)[..., None] * 0.65

    px, pz, dist = floor_plane(dx, dy, dz)
    tile = (np.floor(px * 0.8) + np.floor(pz * 0.8)) % 2.0
    ground = np.where(tile[..., None] > 0.5,
                      np.array([40.0, 34.0, 31.0]), np.array([52.0, 45.0, 40.0]))
    seam = np.minimum(np.abs(px * 0.8 - np.round(px * 0.8)),
                      np.abs(pz * 0.8 - np.round(pz * 0.8)))
    ground += (np.array([96.0, 78.0, 62.0]) - ground) * \
        np.clip(1.0 - seam * 30.0, 0.0, 1.0)[..., None] * 0.5
    ground += (np.array([58.0, 44.0, 36.0]) - ground) * \
        np.clip(dist / 22.0, 0.0, 1.0)[..., None]
    img = np.where((dy > 0.0)[..., None], img, ground)

    # Monoliths every 30°, leaving the exits at 0° and 180° open.
    for k in range(12):
        centre = k * 30.0
        if min(abs(centre), abs(centre - 180.0), abs(centre - 360.0)) < 1.0:
            continue
        delta = (lon_deg - centre + 180.0) % 360.0 - 180.0
        half = 6.2
        slab = (np.abs(delta) < half) & (lat_deg > -15.0) & (lat_deg < 30.0)
        # Fake cylindrical shading: bright down the middle, falling off at the edges.
        shade = np.cos(np.clip(delta / half, -1.0, 1.0) * 1.15) ** 1.6
        face = np.array([116.0, 104.0, 96.0]) * shade[..., None] + np.array([14.0, 12.0, 12.0])
        # Darken towards the top so they recede into the ceiling.
        face *= np.clip(1.0 - (lat_deg + 15.0) / 70.0, 0.35, 1.0)[..., None]
        img = np.where(slab[..., None], face, img)

    return img


SCENES = {"hub": hub, "void": void, "hall": hall}


# ---------------------------------------------------------------------------

def write_png(path: str, rgb: np.ndarray) -> None:
    h, w, _ = rgb.shape
    # Per-row "sub" filter: neighbouring pixels are near-identical across these
    # gradients, so this compresses far better than storing raw rows.
    sub = rgb.astype(np.int16)
    sub[:, 1:] -= rgb[:, :-1].astype(np.int16)
    rows = np.empty((h, 1 + w * 3), np.uint8)
    rows[:, 0] = 1                                    # filter type: sub
    rows[:, 1:] = sub.astype(np.uint8).reshape(h, -1)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data +
                struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(rows.tobytes(), 9))
           + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)


def main(argv) -> int:
    wanted = argv or list(SCENES)
    unknown = [n for n in wanted if n not in SCENES]
    if unknown:
        print(f"unknown room(s): {', '.join(unknown)}", file=sys.stderr)
        print(f"available: {', '.join(SCENES)}", file=sys.stderr)
        return 1

    for name in wanted:
        out = f"images/pano-{name}.png"
        write_png(out, np.clip(SCENES[name](), 0.0, 255.0).astype(np.uint8))
        print(f"wrote {out} ({W}x{H})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

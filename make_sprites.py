#!/usr/bin/env python3
"""Generate placeholder prop sprites in images/ (transparent PNGs).

Props are clickable images anchored in a room — a figure standing on the
plain, an object on a plinth — as opposed to the panoramas themselves. These
are stand-ins until real art exists.

    ./make_sprites.py            # writes every sprite
    ./make_sprites.py figure     # writes just images/sprite-figure.png

Only needs numpy — PNG (RGBA) is encoded here with zlib to avoid a Pillow
dependency. Add a sprite by writing a function and listing it in SPRITES.
"""

import struct
import sys
import zlib

import numpy as np


def capsule(X, Y, ax, ay, bx, by, r):
    """Signed distance to a thick line segment (a rounded limb)."""
    pax, pay = X - ax, Y - ay
    bax, bay = bx - ax, by - ay
    denom = bax * bax + bay * bay
    h = np.clip((pax * bax + pay * bay) / denom, 0.0, 1.0) if denom > 0 else 0.0
    dx, dy = pax - bax * h, pay - bay * h
    return np.sqrt(dx * dx + dy * dy) - r


def figure():
    """A lone humanoid silhouette, feet at the bottom edge of the frame."""
    W, H = 360, 720
    xs = (np.arange(W) - W / 2) / H          # keep circles round: scale x by H
    ys = np.arange(H) / H
    X, Y = np.meshgrid(xs, ys)

    # (ax, ay) → (bx, by) segments with radius r, in H-normalised units.
    parts = [
        (0.0,   0.135, 0.0,   0.135, 0.072),  # head
        (0.0,   0.215, 0.0,   0.520, 0.088),  # torso
        (-0.028, 0.500, -0.055, 0.930, 0.045),  # left leg
        (0.028, 0.500, 0.055, 0.930, 0.045),   # right leg
        (-0.020, 0.250, -0.118, 0.530, 0.036),  # left arm
        (0.020, 0.250, 0.118, 0.530, 0.036),   # right arm
    ]
    d = np.full((H, W), 1e9)
    for (ax, ay, bx, by, r) in parts:
        d = np.minimum(d, capsule(X, Y, ax, ay, bx, by, r))

    # Anti-aliased coverage: solid inside, a soft ramp across the edge.
    edge = 2.5 / H
    alpha = np.clip(-d / edge + 0.5, 0.0, 1.0)

    # Dark charcoal body, lit a little toward the head.
    light = np.clip(1.0 - Y * 0.6, 0.35, 1.0)
    col = np.array([30.0, 28.0, 34.0])[None, None, :] * (0.6 + 0.5 * light)[..., None]

    # Cool rim just inside the silhouette so it reads against a bright sky.
    inside = np.clip(-d, 0.0, None)
    rim = np.clip(1.0 - inside / (7.0 / H), 0.0, 1.0)
    col += np.array([120.0, 126.0, 146.0])[None, None, :] * (rim * alpha)[..., None] * 0.5

    rgb = np.clip(col, 0, 255).astype(np.uint8)
    a = np.clip(alpha * 255.0, 0, 255).astype(np.uint8)
    return np.dstack([rgb, a])


SPRITES = {"figure": figure}


# ---------------------------------------------------------------------------

def write_png_rgba(path: str, rgba: np.ndarray) -> None:
    h, w, _ = rgba.shape
    sub = rgba.astype(np.int16)
    sub[:, 1:] -= rgba[:, :-1].astype(np.int16)   # per-row "sub" filter
    rows = np.empty((h, 1 + w * 4), np.uint8)
    rows[:, 0] = 1
    rows[:, 1:] = sub.astype(np.uint8).reshape(h, -1)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data +
                struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))  # 6 = RGBA
           + chunk(b"IDAT", zlib.compress(rows.tobytes(), 9))
           + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)


def main(argv) -> int:
    wanted = argv or list(SPRITES)
    unknown = [n for n in wanted if n not in SPRITES]
    if unknown:
        print(f"unknown sprite(s): {', '.join(unknown)}", file=sys.stderr)
        print(f"available: {', '.join(SPRITES)}", file=sys.stderr)
        return 1
    for name in wanted:
        out = f"images/sprite-{name}.png"
        rgba = SPRITES[name]()
        write_png_rgba(out, rgba)
        print(f"wrote {out} ({rgba.shape[1]}x{rgba.shape[0]})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

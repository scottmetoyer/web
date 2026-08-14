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
# PNG in and out, by hand, so nothing here needs Pillow. add_prop.py and
# make_panos.py share these.
# ---------------------------------------------------------------------------

CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}            # PNG colour type -> samples/pixel


def read_png_rgba(path):
    """Minimal 8-bit PNG decoder → RGBA (the counterpart to write_png_rgba).

    Handles grey / RGB / palette / grey+alpha / RGBA, since `sips` hands back
    plain RGB for a JPEG and palette PNGs turn up in the wild. Not interlaced.
    """
    data = open(path, "rb").read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        sys.exit(f"not a PNG: {path}")
    pos, idat, plte, trns = 8, b"", None, None
    while pos < len(data):
        (n,) = struct.unpack(">I", data[pos:pos + 4])
        tag, body = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + n]
        if tag == b"IHDR":
            w, h, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", body)
            if depth != 8 or interlace or ctype not in CHANNELS:
                sys.exit(f"unsupported PNG (depth={depth} colour={ctype} interlace={interlace})")
        elif tag == b"PLTE":
            plte = np.frombuffer(body, np.uint8).reshape(-1, 3)
        elif tag == b"tRNS":
            trns = np.frombuffer(body, np.uint8)
        elif tag == b"IDAT":
            idat += body
        pos += 12 + n

    ch = CHANNELS[ctype]
    raw, stride = zlib.decompress(idat), w * ch
    out = np.zeros((h, stride), np.uint8)
    prev = np.zeros(stride, np.int32)
    for y in range(h):
        f = raw[y * (stride + 1)]
        line = np.frombuffer(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)], np.uint8).astype(np.int32).copy()
        if f == 1:                                   # sub
            for x in range(ch, stride):
                line[x] = (line[x] + line[x - ch]) & 255
        elif f == 2:                                 # up
            line = (line + prev) & 255
        elif f == 3:                                 # average
            for x in range(stride):
                left = line[x - ch] if x >= ch else 0
                line[x] = (line[x] + ((left + prev[x]) >> 1)) & 255
        elif f == 4:                                 # paeth
            for x in range(stride):
                a = int(line[x - ch]) if x >= ch else 0
                b, c = int(prev[x]), int(prev[x - ch]) if x >= ch else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        prev = line
        out[y] = line.astype(np.uint8)

    px = out.reshape(h, w, ch)
    if ctype == 3:                                   # palette
        idx = px[:, :, 0]
        rgb = plte[idx]
        alpha = (trns[idx] if trns is not None and len(trns) > int(idx.max())
                 else np.full((h, w), 255, np.uint8))
        return np.dstack([rgb, alpha])
    if ctype == 0:
        return np.dstack([px[:, :, 0]] * 3 + [np.full((h, w), 255, np.uint8)])
    if ctype == 4:
        return np.dstack([px[:, :, 0]] * 3 + [px[:, :, 1]])
    if ctype == 2:
        return np.dstack([px, np.full((h, w), 255, np.uint8)])
    return px


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

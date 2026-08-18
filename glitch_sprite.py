#!/usr/bin/env python3
"""Corrupt a prop sprite by layering geometric fragments of other art onto it.

The man in the suit is infested with insect parts; the old PC is overgrown with
flowers; Snake Mountain has bodybuilders' arms and legs erupting out of it. Each
one is the same operation: cut random rotated shards — rectangles, triangles,
wedges, sheared bars — out of a pile of donor images, and composite them over
the base sprite.

    ./glitch_sprite.py images/sprite-suit.png --name suit-glitch \\
        --donor oc:239649/dogface-butterfly --donor oc:316155/wasp \\
        --fragments 22 --seed 7 --webp 90

DONOR sources are whatever `add_prop.py` accepts — `oc:ID/slug`,
`commons:File:…`, a URL, or a local path — and are cached rasterised under
/tmp/glitch-donors, so re-rolling `--seed` costs nothing after the first run.

Two things are deliberate:

- **The output keeps the base's exact dimensions.** A prop anchors at its
  bottom-centre, so padding the canvas to fit an overhanging shard would move
  the figure's feet and silently shift where the prop sits in the room. Shards
  that hang past the edge are clipped instead.
- **Most shards are clipped to the base's own alpha**, so the silhouette still
  reads as a man / a computer / a mountain. `--bleed` is the fraction allowed
  to break that outline, which is what stops it looking like a texture fill.

Stdlib + numpy, and the fetch/raster/credit machinery is reused from add_prop.
"""

import argparse
import json
import os
import re
import sys
import tempfile
import time

import numpy as np

from add_prop import (ROOT, crop_to_alpha, encode_webp, knockout_white,
                      rasterise, record_credit, resolve, run)
from make_sprites import read_png_rgba, write_png_rgba

CACHE = os.path.join(tempfile.gettempdir(), "glitch-donors")

# How a shard is cut. Names are used in the --shapes flag.
SHAPES = ("rect", "tri", "wedge", "shear")
# What is done to its pixels afterwards. "plain" is weighted up so the donor
# art stays legible — all-treatment looks like noise, not like contamination.
TREATMENTS = ("plain", "plain", "plain", "shift", "invert", "posterize", "scan")


# --- loading ----------------------------------------------------------------

def load_rgba(path):
    """Any sprite on disk → RGBA. WebP via dwebp, other formats via sips."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".png":
        return read_png_rgba(path)
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "out.png")
        if ext == ".webp":
            run(["dwebp", "-quiet", path, "-o", out])
        else:
            run(["sips", "-s", "format", "png", path, "--out", out])
        return read_png_rgba(out)


def donor(source, px, knockout):
    """SOURCE → (RGBA cropped to its alpha, credit dict), cached on disk.

    The cache key includes the raster settings, so changing --donor-px or the
    knockout tolerance re-fetches rather than silently reusing the old cut.
    """
    tag = re.sub(r"\W+", "-", source).strip("-")[:80]
    tag += f"-{px}" + (f"-k{knockout}" if knockout is not None else "")
    png, meta = os.path.join(CACHE, tag + ".png"), os.path.join(CACHE, tag + ".json")
    if os.path.exists(png) and os.path.exists(meta):
        return read_png_rgba(png), json.load(open(meta))

    print(f"  fetching {source}")
    # Openclipart resets connections and 500s often enough that one try is a
    # coin flip; with a pool of donors that is a near-certain failure per run.
    for attempt in range(8):
        try:
            data, suffix, credit = resolve(source)
            break
        except Exception as exc:
            if attempt == 7:
                sys.exit(f"couldn't fetch {source}: {exc}")
            print(f"    retrying ({exc})")
            time.sleep(1.5 * (attempt + 1))
    rgba = rasterise(data, suffix, px)
    if knockout is not None:
        rgba = knockout_white(rgba, knockout)
    rgba = crop_to_alpha(rgba)
    os.makedirs(CACHE, exist_ok=True)
    write_png_rgba(png, rgba)
    json.dump(credit, open(meta, "w"))
    return rgba, credit


# --- cutting ----------------------------------------------------------------

def shape_mask(u, v, shape, rng):
    """Which pixels of the shard's own frame survive. u, v span [-1, 1]."""
    if shape == "rect":
        return np.ones(u.shape, bool)
    if shape == "tri":
        return np.abs(u) <= (v + 1) / 2                    # apex up, base down
    if shape == "shear":
        return np.abs(u - 0.55 * v) <= 0.62                # a leaning bar
    start = rng.uniform(0, 2 * np.pi)                      # "wedge": a pie slice
    return (((np.arctan2(v, u) - start) % (2 * np.pi)) <= rng.uniform(0.6, 1.8)) \
        & (u * u + v * v <= 1.0)


def cut(src, cx, cy, w, h, angle, shape, rng):
    """A w×h shard of `src`, centred on (cx, cy) and rotated by `angle`.

    Sampled by inverse mapping — every output pixel asks where it came from —
    so the rotation costs one gather and never leaves holes. Anything that
    lands outside the donor, or outside the shape, comes back transparent.
    """
    ys, xs = np.mgrid[0:h, 0:w]
    u = (xs + 0.5) / w * 2 - 1
    v = (ys + 0.5) / h * 2 - 1
    ca, sa = np.cos(angle), np.sin(angle)
    dx, dy = u * w / 2, v * h / 2
    sx = np.rint(cx + dx * ca - dy * sa).astype(int)
    sy = np.rint(cy + dx * sa + dy * ca).astype(int)
    inside = (sx >= 0) & (sx < src.shape[1]) & (sy >= 0) & (sy < src.shape[0])
    out = src[sy.clip(0, src.shape[0] - 1), sx.clip(0, src.shape[1] - 1)].copy()
    out[~(inside & shape_mask(u, v, shape, rng)), 3] = 0
    return out


def in_region(src, cx, cy, region):
    """Where in the donor a shard is allowed to come from.

    "limbs" is the whole point of the Snake Mountain pass: in a standing figure
    the arms are out at the sides and the legs are down low, so restricting the
    cut to the outer thirds or the bottom third gets arms and legs rather than
    another torso.
    """
    if region == "any":
        return True
    x, y = cx / src.shape[1], cy / src.shape[0]
    return abs(x - 0.5) > 0.26 or y > 0.58


def treat(frag, kind, rng):
    """Glitch the shard's pixels in place."""
    rgb = frag[:, :, :3].astype(np.int16)
    if kind == "shift":                      # channel separation
        d = int(rng.integers(2, 7))
        rgb[:, :, 0] = np.roll(rgb[:, :, 0], d, 1)
        rgb[:, :, 2] = np.roll(rgb[:, :, 2], -d, 1)
    elif kind == "invert":
        rgb = 255 - rgb
    elif kind == "posterize":
        rgb = (rgb // 72) * 72 + 36
    elif kind == "scan":                     # drop every other row
        frag[::2, :, 3] = 0
    frag[:, :, :3] = rgb.clip(0, 255).astype(np.uint8)
    return frag


# --- compositing ------------------------------------------------------------

def over(canvas, frag, x0, y0, clip, opacity):
    """Composite `frag` onto `canvas` at (x0, y0), clipped to the canvas.

    Straight non-premultiplied "over". `clip` is the base alpha the shard is
    held inside (None to let it break the silhouette).
    """
    h, w = frag.shape[:2]
    sx0, sy0 = max(0, -x0), max(0, -y0)
    x0, y0 = max(0, x0), max(0, y0)
    w = min(w - sx0, canvas.shape[1] - x0)
    h = min(h - sy0, canvas.shape[0] - y0)
    if w <= 0 or h <= 0:
        return 0.0
    frag = frag[sy0:sy0 + h, sx0:sx0 + w]

    dst = canvas[y0:y0 + h, x0:x0 + w]
    fa = frag[:, :, 3:4].astype(np.float32) / 255.0 * opacity
    if clip is not None:
        fa = fa * (clip[y0:y0 + h, x0:x0 + w, None].astype(np.float32) / 255.0)
    ba = dst[:, :, 3:4].astype(np.float32) / 255.0
    oa = fa + ba * (1 - fa)
    rgb = (frag[:, :, :3] * fa + dst[:, :, :3] * ba * (1 - fa)) / np.maximum(oa, 1e-6)
    dst[:, :, :3] = rgb.clip(0, 255).astype(np.uint8)
    dst[:, :, 3:4] = (oa * 255).clip(0, 255).astype(np.uint8)
    return float(fa.mean() * h * w)


# --- the pass ---------------------------------------------------------------

def glitch(base, donors, a):
    """Layer `a.fragments` shards of `donors` over a copy of `base`."""
    rng = np.random.default_rng(a.seed)
    out = base.copy()
    solid = base[:, :, 3] > 128
    ys, xs = np.nonzero(solid)
    if not len(ys):
        sys.exit("the base sprite is fully transparent")
    scale = float(np.sqrt(base.shape[0] * base.shape[1]))   # size shards by this
    shapes = a.shapes.split(",")
    covered, kinds = 0.0, {}

    for i in range(a.fragments):
        src, _ = donors[int(rng.integers(len(donors)))]
        shape = shapes[int(rng.integers(len(shapes)))]
        size = scale * rng.uniform(a.frag_min, a.frag_max)
        aspect = rng.uniform(0.45, 2.2)
        fw = max(4, int(size * np.sqrt(aspect)))
        fh = max(4, int(size / np.sqrt(aspect)))

        # Find somewhere in the donor worth cutting: inside the allowed region,
        # and actually holding some art rather than a mouthful of empty air.
        frag = None
        for _ in range(80):
            cx = int(rng.integers(src.shape[1]))
            cy = int(rng.integers(src.shape[0]))
            if not in_region(src, cx, cy, a.region):
                continue
            trial = cut(src, cx, cy, fw, fh, rng.uniform(0, 2 * np.pi), shape, rng)
            if (trial[:, :, 3] > 8).mean() >= a.min_cover:
                frag = trial
                break
        if frag is None:
            continue

        kind = TREATMENTS[int(rng.integers(len(TREATMENTS)))]
        frag = treat(frag, kind, rng)
        kinds[kind] = kinds.get(kind, 0) + 1

        # Land it on a pixel of the figure, jittered by up to half a shard so
        # things straddle edges instead of all sitting dead centre.
        j = int(rng.integers(len(ys)))
        x = int(xs[j] - fw / 2 + rng.uniform(-0.5, 0.5) * fw)
        y = int(ys[j] - fh / 2 + rng.uniform(-0.5, 0.5) * fh)
        bleeds = rng.random() < a.bleed
        covered += over(out, frag, x, y, None if bleeds else base[:, :, 3],
                        rng.uniform(a.opacity_min, 1.0))

    pct = covered / (base.shape[0] * base.shape[1]) * 100
    print(f"  layered {a.fragments} shards over {pct:.0f}% of the frame "
          f"({', '.join(f'{k}×{v}' for k, v in sorted(kinds.items()))})")
    return out


def main(argv):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog=__doc__)
    p.add_argument("base", help="the sprite to corrupt, e.g. images/sprite-suit.png")
    p.add_argument("--name", required=True, help="writes images/sprite-<name>.<ext>")
    p.add_argument("--donor", action="append", required=True, metavar="SOURCE",
                   help="art to cut fragments from; repeat for a pool")
    p.add_argument("--fragments", type=int, default=20)
    p.add_argument("--seed", type=int, default=1, help="re-roll the same recipe")
    p.add_argument("--region", choices=["any", "limbs"], default="any",
                   help="'limbs' cuts only from a figure's arms and legs")
    p.add_argument("--shapes", default=",".join(SHAPES))
    p.add_argument("--frag-min", type=float, default=0.09,
                   help="shard size, as a fraction of sqrt(w*h) of the base")
    p.add_argument("--frag-max", type=float, default=0.26)
    p.add_argument("--bleed", type=float, default=0.16,
                   help="fraction of shards allowed past the silhouette")
    p.add_argument("--opacity-min", type=float, default=0.7)
    p.add_argument("--min-cover", type=float, default=0.35,
                   help="reject a cut that is mostly transparent")
    p.add_argument("--donor-px", type=int, default=900, help="donor raster height")
    p.add_argument("--knockout-white", nargs="?", type=int, const=12, default=None,
                   metavar="TOL", help="flood-fill donors' white backgrounds away")
    p.add_argument("--webp", nargs="?", type=int, const=90, default=None, metavar="Q")
    p.add_argument("--force", action="store_true")
    a = p.parse_args(argv)

    base = load_rgba(a.base if os.path.isabs(a.base) else os.path.join(ROOT, a.base))
    print(f"base {os.path.basename(a.base)}: {base.shape[1]}x{base.shape[0]}")
    donors = [donor(s, a.donor_px, a.knockout_white) for s in a.donor]
    print(f"  {len(donors)} donors")

    out = glitch(base, donors, a)

    png = os.path.join(ROOT, "images", f"sprite-{a.name}.png")
    final = os.path.splitext(png)[0] + (".webp" if a.webp else ".png")
    if os.path.exists(final) and not a.force:
        sys.exit(f"{os.path.relpath(final, ROOT)} exists (use --force)")
    write_png_rgba(png, out)
    final = encode_webp(png, a.webp) if a.webp else png
    name = os.path.basename(final)
    print(f"  wrote images/{name} ({os.path.getsize(final) // 1024}KB)")

    # Repeating a --donor is how you weight the pool toward it, so the credits
    # have to be deduped or a favoured source gets thanked three times.
    seen, credits = set(), []
    for _, c in donors:
        if c["page"] not in seen:
            seen.add(c["page"])
            credits.append(c)
    record_credit(name[len("sprite-"):], credits,
                  f"Fragments of the above, cut as rotated {a.shapes.replace(',', '/')} "
                  f"sections and layered over `{os.path.basename(a.base)}` by "
                  f"`glitch_sprite.py --seed {a.seed} --fragments {a.fragments}"
                  f"{f' --region {a.region}' if a.region != 'any' else ''}`. "
                  f"Same dimensions as the base, so the prop's anchor is unchanged.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

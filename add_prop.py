#!/usr/bin/env python3
"""Find art, turn it into a prop sprite, and wire it into a room.

The three annoying steps of "put a thing in the world" — finding an image you
are actually allowed to use, cutting it out cleanly, and hand-writing the
`<button class="prop">` — done in one command.

    # 1. look for something (openclipart is CC0 across the board)
    ./add_prop.py search "businessman" --preview
    #    → renders candidates to /tmp/prop-preview/ so you can look at them

    # 2. plant the one you liked
    ./add_prop.py add oc:337378 --name suit --room index.html \\
        --yaw 24 --pitch -20 --height 34 \\
        --alt "A man in a suit" --title "Someone" \\
        --body "<p>He has nothing to say yet.</p>"

    # …or from a file on this machine, or any URL
    ./add_prop.py add ~/Pictures/statue.png --name statue --yaw 90 --pitch -14
    ./add_prop.py add https://example.com/thing.svg --name thing --knockout-white

SOURCE is one of:
    oc:337378                     openclipart id (CC0)
    https://openclipart.org/…     openclipart page or download link
    commons:File:Foo.svg          Wikimedia Commons (license is checked & shown)
    https://…/anything.png        any URL
    ./local/file.{svg,png,jpg,…}  a file on this machine

What `add` does: fetches the source, rasterises it (`rsvg-convert` for SVG,
`sips` for everything else), optionally knocks out a white background, crops to
the alpha bounding box so the sprite's bottom edge is the figure's feet, writes
`images/sprite-<name>.png`, appends provenance to `images/CREDITS.md`, and
inserts the prop into the room's `<div id="props">`.

Stdlib + numpy only, like the rest of this repo. PNG decoding lives here; the
encoder is reused from make_sprites.py.
"""

import argparse
import html
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import zlib

import numpy as np

from make_sprites import write_png_rgba

UA = {"User-Agent": "scottmetoyer-web/1.0 (https://github.com/scottmetoyer)"}
ROOT = os.path.dirname(os.path.abspath(__file__))
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
FREE = ("public domain", "cc0", "publicdomain")   # licenses that need no attribution


# --- fetching ---------------------------------------------------------------

def get(url, binary=False, timeout=40):
    return fetch(url, timeout)[0] if binary else fetch(url, timeout)[0].decode("utf-8", "replace")


def fetch(url, timeout=40):
    """→ (bytes, final url). The final url matters: openclipart redirects a
    guessed download link to the canonical one, which is how we learn the slug."""
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.url


def commons_api(**kw):
    kw.setdefault("format", "json")
    kw.setdefault("action", "query")
    return json.loads(get(COMMONS_API + "?" + urllib.parse.urlencode(kw)))


def search_openclipart(query, limit):
    """Openclipart's JSON API is gone; the search page still works. All CC0."""
    page = get("https://openclipart.org/search/?" + urllib.parse.urlencode({"query": query}))
    hits, seen = [], set()
    for cid, slug in re.findall(r"/detail/(\d+)/([\w\-%.]+)", page):
        if cid in seen:
            continue
        seen.add(cid)
        hits.append({
            "id": f"oc:{cid}/{slug}",     # id+slug so `add` gets the metadata free
            "title": urllib.parse.unquote(slug).replace("-", " "),
            "license": "CC0 (public domain)",
            "url": f"https://openclipart.org/download/{cid}/{slug}.svg",
            "page": f"https://openclipart.org/detail/{cid}/{slug}",
        })
        if len(hits) >= limit:
            break
    return hits


def search_commons(query, limit):
    """Commons has photos too, but most usable clipart there is CC BY-SA."""
    res = commons_api(list="search", srnamespace=6, srlimit=limit * 3,
                      srsearch=f"{query} filetype:drawing|bitmap")
    titles = [p["title"] for p in res["query"]["search"]]
    hits = []
    for i in range(0, len(titles), 20):
        info = commons_api(prop="imageinfo", iiprop="url|size|extmetadata",
                           titles="|".join(titles[i:i + 20]))
        for p in info["query"]["pages"].values():
            ii = (p.get("imageinfo") or [{}])[0]
            meta = ii.get("extmetadata", {})
            hits.append({
                "id": "commons:" + p["title"],
                "title": p["title"].removeprefix("File:"),
                "license": meta.get("LicenseShortName", {}).get("value", "?"),
                "url": ii.get("url", "").split("?")[0],
                "page": "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(p["title"]),
                "size": f"{ii.get('width')}x{ii.get('height')}",
            })
    return hits[:limit]


def resolve(source):
    """SOURCE → (bytes, suffix, credit dict). Local files are read as-is."""
    if os.path.exists(os.path.expanduser(source)):
        path = os.path.expanduser(source)
        with open(path, "rb") as f:
            data = f.read()
        return data, os.path.splitext(path)[1].lower(), {
            "title": os.path.basename(path), "author": "unrecorded",
            "license": "local file — set with --license if it matters", "page": path}

    m = re.match(r"^oc:(\d+)(?:/([\w\-%.]+))?$", source) or \
        re.match(r"^https?://openclipart\.org/(?:detail|download)/(\d+)/([\w\-%.]+?)(?:\.svg)?$", source)
    if m:
        cid, slug = m.group(1), m.group(2)
        # A slug-less /detail/ URL just redirects to the homepage, so get the
        # canonical slug from the download redirect before asking for metadata.
        data, final = fetch(f"https://openclipart.org/download/{cid}/{slug or 'x'}.svg")
        slug = (re.search(r"/download/\d+/([\w\-%.]+)\.svg", final) or [None, slug or "art"])[1]
        page_html = get(f"https://openclipart.org/detail/{cid}/{slug}")
        author = (re.search(r"/artist/([\w\-%.]+)", page_html) or [None, "unknown"])[1]
        title = (re.search(r"<title>([^<]*?)\s*-\s*Openclipart</title>", page_html)
                 or [None, slug.replace("-", " ")])[1]
        return data, ".svg", {"title": title, "author": author,
                              "license": "Public domain (CC0 1.0)",
                              "page": f"https://openclipart.org/detail/{cid}/{slug}"}

    if source.startswith("commons:"):
        title = source[len("commons:"):]
        if not title.startswith("File:"):
            title = "File:" + title
        info = commons_api(prop="imageinfo", iiprop="url|extmetadata", titles=title)
        page = next(iter(info["query"]["pages"].values()))
        if "imageinfo" not in page:
            sys.exit(f"no such Commons file: {title}")
        ii = page["imageinfo"][0]
        meta = ii.get("extmetadata", {})
        lic = meta.get("LicenseShortName", {}).get("value", "?")
        author = re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", "unknown")).strip()
        if not any(f in lic.lower() for f in FREE):
            print(f"  ! {lic} — this one needs attribution (and share-alike, if BY-SA).",
                  file=sys.stderr)
        url = ii["url"].split("?")[0]
        return get(url, binary=True), os.path.splitext(url)[1].lower(), {
            "title": title.removeprefix("File:"), "author": author, "license": lic,
            "page": "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(title)}

    if source.startswith(("http://", "https://")):
        url = source.split("?")[0]
        return get(source, binary=True), os.path.splitext(url)[1].lower() or ".png", {
            "title": os.path.basename(url), "author": "unknown",
            "license": "UNVERIFIED — check before publishing", "page": source}

    sys.exit(f"don't know how to fetch: {source}")


# --- raster -----------------------------------------------------------------

def rasterise(data, suffix, px):
    """Anything → an RGBA array `px` tall. SVG via rsvg-convert, else sips."""
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "in" + (suffix or ".png"))
        out = os.path.join(tmp, "out.png")
        with open(src, "wb") as f:
            f.write(data)
        if suffix == ".svg":
            if not shutil.which("rsvg-convert"):
                sys.exit("need rsvg-convert for SVG sources: brew install librsvg")
            run(["rsvg-convert", "-h", str(px), "-o", out, src])
        else:
            run(["sips", "-s", "format", "png", "--resampleHeight", str(px), src, "--out", out])
        return read_png_rgba(out)


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode:
        sys.exit(f"{cmd[0]} failed: {p.stderr.strip() or p.stdout.strip()}")


CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}            # PNG colour type → samples/pixel


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


def knockout_white(rgba, tol):
    """Make the white *background* transparent — flood filled in from the edges,
    so a white shirt or an eye highlight inside the figure survives."""
    h, w, _ = rgba.shape
    near_white = rgba[:, :, :3].min(axis=2) >= 255 - tol
    bg = np.zeros((h, w), bool)
    stack = [(x, y) for y in (0, h - 1) for x in range(w) if near_white[y, x]]
    stack += [(x, y) for x in (0, w - 1) for y in range(h) if near_white[y, x]]
    while stack:                                     # scanline flood fill
        x, y = stack.pop()
        if bg[y, x] or not near_white[y, x]:
            continue
        x0 = x
        while x0 > 0 and near_white[y, x0 - 1] and not bg[y, x0 - 1]:
            x0 -= 1
        x1 = x
        while x1 < w - 1 and near_white[y, x1 + 1] and not bg[y, x1 + 1]:
            x1 += 1
        bg[y, x0:x1 + 1] = True
        for ny in (y - 1, y + 1):
            if 0 <= ny < h:
                row = near_white[ny, x0:x1 + 1] & ~bg[ny, x0:x1 + 1]
                stack += [(x0 + int(i), ny) for i in np.flatnonzero(row)]
    out = rgba.copy()
    out[bg, 3] = 0
    # Soften the 1px ring left behind, so cutouts don't get a hard white fringe.
    ring = np.zeros((h, w), bool)
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        ring |= np.roll(bg, (dy, dx), (0, 1))
    ring &= ~bg
    whiteness = out[:, :, :3].min(axis=2).astype(np.float32) / 255.0
    out[ring, 3] = np.clip((1.0 - whiteness[ring]) * 2.0, 0, 1) * 255
    print(f"  knocked out {bg.mean():.0%} of the frame as background")
    return out


def crop_to_alpha(rgba):
    ys, xs = np.where(rgba[:, :, 3] > 8)
    if not len(ys):
        sys.exit("image is fully transparent")
    return rgba[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


# --- wiring -----------------------------------------------------------------

PROP = '''  <button class="prop" data-src="images/sprite-{name}.png" data-alt="{alt}"
          data-yaw="{yaw:g}" data-pitch="{pitch:g}" data-height="{height:g}"{anchor}>
    <template>
      <h2>{title}</h2>
      {body}
    </template>
  </button>
'''


def prop_html(a):
    return PROP.format(
        name=a.name, alt=html.escape(a.alt or a.name), yaw=a.yaw, pitch=a.pitch,
        height=a.height, title=html.escape(a.title or a.name),
        anchor='' if a.anchor == "bottom" else f' data-anchor="{a.anchor}"',
        body=a.body or "<p>Nothing to say yet.</p>")


def wire_into_room(room, name, snippet, force):
    path = os.path.join(ROOT, room)
    if not os.path.exists(path):
        sys.exit(f"no such room: {room}")
    src = open(path).read()

    # Already there? Replacing lets you re-run `add` to nudge yaw/pitch/height —
    # but it overwrites hand-edited dialog content, so it needs --force.
    here = re.search(rf'[ \t]*<button class="prop" data-src="images/sprite-{re.escape(name)}\.png".*?</button>\n',
                     src, re.S)
    if here:
        if not force:
            print(f"  ! {room} already has a '{name}' prop — pass --force to replace it")
            return
        open(path, "w").write(src.replace(here.group(0), snippet, 1))
        print(f"  replaced the '{name}' prop in {room} (dialog content overwritten)")
        return

    if '<div id="props">' in src:
        out = re.sub(r'(<div id="props">.*?)(\n</div>)', lambda m: m.group(1) + "\n" + snippet.rstrip("\n") + m.group(2),
                     src, count=1, flags=re.S)
    else:
        block = f'<div id="props">\n{snippet}</div>\n\n'
        anchor = '<nav id="hotspots">' if '<nav id="hotspots">' in src else "</body>"
        out = src.replace(anchor, block + anchor, 1)
    if out == src:
        sys.exit(f"couldn't find anywhere to insert the prop in {room}")
    open(path, "w").write(out)
    print(f"  wired into {room}")


def record_credit(name, credit, note):
    path = os.path.join(ROOT, "images", "CREDITS.md")
    head = "# Image credits\n\nWhere the art in this folder came from. Generated placeholders\n(`make_panos.py`, `make_sprites.py`) are not listed — they are ours.\n"
    body = open(path).read() if os.path.exists(path) else head
    entry = (f"\n## `sprite-{name}.png`\n\n"
             f"\"{credit['title']}\", by *{credit['author']}* — {credit['page']}\n\n"
             f"License: {credit['license']}\n\n{note}\n")
    # Re-adding a sprite replaces its credit rather than stacking a second one.
    existing = re.search(rf"\n## `sprite-{re.escape(name)}\.png`\n.*?(?=\n## |\Z)", body, re.S)
    body = body.replace(existing.group(0), "") if existing else body
    open(path, "w").write(body.rstrip("\n") + "\n" + entry)
    print("  credited in images/CREDITS.md")


# --- commands ---------------------------------------------------------------

def cmd_search(a):
    hits = (search_commons if a.source == "commons" else search_openclipart)(a.query, a.limit)
    if not hits:
        return print("nothing found")
    for h_ in hits:
        print(f"{h_['id']:<28} {h_['license']:<22} {h_['title']}")
    if a.preview:
        os.makedirs(a.preview_dir, exist_ok=True)
        print(f"\nrendering previews → {a.preview_dir}")
        for h_ in hits[:a.limit]:
            tag = re.sub(r"\W+", "-", h_["id"])
            try:
                data, suffix, _ = resolve(h_["id"])
                write_png_rgba(os.path.join(a.preview_dir, f"{tag}.png"),
                               rasterise(data, suffix, 420))
                print(f"  {tag}.png  {h_['title']}")
            except Exception as exc:                 # a dud candidate shouldn't stop the sweep
                print(f"  {tag}: skipped ({exc})")


def cmd_add(a):
    print(f"fetching {a.source}")
    data, suffix, credit = resolve(a.source)
    credit.update({k: v for k, v in
                   (("author", a.author), ("license", a.license)) if v})
    rgba = rasterise(data, suffix, a.px)
    print(f"  rasterised {rgba.shape[1]}x{rgba.shape[0]}")
    if a.knockout_white is not None:
        rgba = knockout_white(rgba, a.knockout_white)
    if not a.no_crop:
        rgba = crop_to_alpha(rgba)
        print(f"  cropped to alpha: {rgba.shape[1]}x{rgba.shape[0]}")
    if (rgba[:, :, 3] > 8).all():
        print("  ! no transparency — this will render as a rectangle."
              " Try --knockout-white, or find an SVG/PNG cutout.")
    out = os.path.join(ROOT, "images", f"sprite-{a.name}.png")
    if os.path.exists(out) and not a.force:
        sys.exit(f"images/sprite-{a.name}.png exists (use --force)")
    write_png_rgba(out, rgba)
    print(f"  wrote images/sprite-{a.name}.png")
    record_credit(a.name, credit,
                  f"Rendered {a.px}px tall, then cropped to its alpha bounding box "
                  f"({rgba.shape[1]}×{rgba.shape[0]}) so the bottom edge is the "
                  f"prop's anchor point.")
    snippet = prop_html(a)
    if a.no_wire:
        print("\n" + snippet)
    else:
        wire_into_room(a.room, a.name, snippet, a.force)
    print(f"\nlook at it:  {a.room}?yaw={a.yaw:g}&pitch={a.pitch:g}&drift=0")


def main(argv):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="look for usable art")
    s.add_argument("query")
    s.add_argument("--source", choices=["openclipart", "commons"], default="openclipart")
    s.add_argument("--limit", type=int, default=12)
    s.add_argument("--preview", action="store_true", help="render candidates to look at")
    s.add_argument("--preview-dir", default="/tmp/prop-preview")
    s.set_defaults(fn=cmd_search)

    d = sub.add_parser("add", help="make a sprite and put it in a room")
    d.add_argument("source", help="oc:ID | commons:File:… | URL | local path")
    d.add_argument("--name", required=True, help="sprite-<name>.png")
    d.add_argument("--room", default="index.html")
    d.add_argument("--yaw", type=float, default=0.0)
    d.add_argument("--pitch", type=float, default=-20.0)
    d.add_argument("--height", type=float, default=34.0, help="size in degrees of view")
    d.add_argument("--anchor", choices=["bottom", "center"], default="bottom")
    d.add_argument("--alt", default="")
    d.add_argument("--title", default="", help="dialog heading")
    d.add_argument("--body", default="", help="dialog HTML (raw, like the editor)")
    d.add_argument("--body-file", help="read dialog HTML from a file")
    d.add_argument("--px", type=int, default=1200, help="raster height before cropping")
    d.add_argument("--author", help="override the credit line (needed for local files)")
    d.add_argument("--license", help="override the recorded license")
    d.add_argument("--knockout-white", nargs="?", type=int, const=12, default=None,
                   metavar="TOL", help="flood-fill a white background to transparent")
    d.add_argument("--no-crop", action="store_true")
    d.add_argument("--no-wire", action="store_true", help="just print the snippet")
    d.add_argument("--force", action="store_true", help="overwrite an existing sprite")
    d.set_defaults(fn=cmd_add)

    a = p.parse_args(argv)
    if getattr(a, "body_file", None):
        a.body = open(os.path.expanduser(a.body_file)).read().strip()
    a.fn(a)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

# scottmetoyer-web

A [Decker](https://beyondloom.com/decker/) deck published as a static website.

## Files

- `site.deck` — the source deck (authored in the Decker app). This is the source of truth for deck content.
- `index.html` — the **exported** deck (Decker "Export HTML"). A single self-contained file: the Decker runtime + the deck data embedded in a `<script language="decker">` block at the top. ~426KB, mostly machine-generated. Do not hand-author deck content here — edit it in Decker and re-export.
- `images/` — image assets referenced by hand edits (e.g. the page background).
- `customize.py` — post-export patch script (see below).
- `pano.html` — standalone drag-around 360° panorama viewer (see below).
- `make_demo_pano.py` — generates `images/demo-pano.png`, the viewer's test image.

## Important: re-exporting clobbers hand edits

Every time the deck is re-exported from Decker, `index.html` is overwritten,
wiping any manual changes (custom CSS, background image, etc.).

**Post-export workflow:**

1. Export the deck from Decker → overwrites `index.html`
2. Run `./customize.py` → reapplies the hand edits

`customize.py` holds a list of `Patch(name, before, after)` exact-string
replacements. It is idempotent and reports the state of each patch
(`applied` / `already applied` / `WARN anchor not found`). A `WARN` (non-zero
exit) means Decker changed the text being matched and the patch's `before`
string needs updating.

**To add a new post-export tweak:** add a `Patch(...)` entry to the `PATCHES`
list in `customize.py` rather than only editing `index.html` directly —
otherwise the next export will lose it.

### Current customizations

- Full-screen background image (`images/abc_cover_notext_variant.jpg`) on
  `<body>`, behind the centered deck canvas.

## 360° panorama viewer (`pano.html`)

A self-contained page, deliberately **outside** the Decker deck: Decker's canvas
is a fixed 512×342 1-bit surface and every re-export clobbers `index.html`, so a
WebGL viewer can't live in there. `pano.html` has no dependencies and no build
step — open it, or link to it from anywhere.

It raycasts an equirectangular (2:1) image in a fragment shader on a fullscreen
triangle, which gives correct rectilinear perspective at any zoom, unlike
scrolling a wide image sideways. WebGL2 is used when available only because it
permits `REPEAT` wrapping on non-power-of-two textures; on WebGL1 the image is
rescaled to a power of two first. Oversized photos are downscaled to the GPU's
`MAX_TEXTURE_SIZE`.

- Drag to look, scroll/pinch to zoom, arrows to nudge; `f` fullscreen,
  `d` 1-bit Bayer dither, `r` reset, space toggles the idle auto-drift.
- **Drag any 360 photo onto the page** to view it — the quickest way to check a
  new image.
- Query params: `?img=images/foo.jpg&yaw=90&pitch=-10&fov=60&dither=1&drift=0`.
  `yaw`/`pitch`/`fov` make specific views linkable and are how the viewer was
  regression-tested with headless screenshots.
- Needs to be served over HTTP — browsers refuse to make WebGL textures from
  `file://`. `python3 -m http.server` is enough; the page says so if it hits it.

Swap in a real panorama by dropping a 2:1 equirectangular JPEG in `images/` and
pointing `SRC`/`?img=` at it. Any 360 camera or a phone's photosphere mode emits
this format.

## Notes

- The deck is `locked:1` in the export.
- This is a static site — no build system, no package manager, no server.
  Just export, patch, and serve the files.

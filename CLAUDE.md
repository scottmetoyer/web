# scottmetoyer-web

A static personal site. No build system, no package manager, no server — just
files. Edit, commit, push; the host serves the folder as-is.

The landing page is an interactive 360° panorama viewer.

## Files

- `index.html` — the site. A self-contained WebGL 360° panorama viewer
  (see below). Hand-authored; edit it directly.
- `images/` — image assets. `demo-pano.png` is the placeholder panorama the
  viewer loads by default.
- `make_demo_pano.py` — regenerates `images/demo-pano.png`.
- `deck.html`, `site.deck`, `index.deck`, `customize.py` — **legacy**, see below.

## The 360° viewer (`index.html`)

Everything is in the one file: markup, CSS, and the GL code. It raycasts an
equirectangular (2:1) image in a fragment shader across a fullscreen triangle,
which gives correct rectilinear perspective at any zoom and pitch — unlike
scrolling a wide image sideways, which looks wrong the moment you look up.

WebGL2 is used when available only because it permits `REPEAT` wrapping on
non-power-of-two textures; on WebGL1 the image is rescaled to a power of two
first. Oversized photos are downscaled to the GPU's `MAX_TEXTURE_SIZE`.

**Controls:** drag to look, scroll/pinch to zoom, arrows to nudge; `f`
fullscreen, `d` 1-bit Bayer dither, `r` reset, space toggles the idle drift.
**Drag any 360 photo onto the page** to view it — the fastest way to check a
new image.

**Query params:** `?img=images/foo.jpg&yaw=90&pitch=-10&fov=60&dither=1&drift=0`.
`yaw`/`pitch`/`fov` make specific views linkable, and are how the viewer gets
regression-tested with headless screenshots (see below).

**Must be served over HTTP** — browsers refuse to build WebGL textures from
`file://`. `python3 -m http.server` is enough; the page says so if it hits it.

### Sign conventions (easy to get backwards)

Both drag axes are "grab the photo and pull": drag right and the scene follows
right, drag down and the sky comes into view. In view state, `yaw` increasing
turns right (east) and `pitch` increasing looks up. The shader's yaw rotation
must be the inverse of the naive one or the whole thing feels like a scrollbar.

### Testing changes

Headless Chrome plus the query params covers most of it — load a known `yaw`
and check the right thing is centered:

    python3 -m http.server 8777 &
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
      --headless=new --disable-gpu --enable-unsafe-swiftshader \
      --window-size=900,560 --virtual-time-budget=6000 \
      --screenshot=out.png "http://localhost:8777/?yaw=90&drift=0"

In `demo-pano.png` the cardinal posts are N=red, E=yellow, S=green, W=blue, so
a screenshot immediately shows whether orientation is right. Note that
`requestAnimationFrame` is throttled under headless virtual time, so the
on-screen readout won't update — screenshot the rendered frame instead of
scraping the DOM.

## Panorama images

The viewer wants **equirectangular 2:1** images (what every 360 camera and
photosphere mode emits). 4096×2048 is a good working size.

Useful to remember when making them: the middle row is the horizon, the top and
bottom rows each collapse to a single point, the left and right edges must wrap,
and vertical lines in the world stay vertical columns in the image while every
other straight line becomes a sine curve.

`make_demo_pano.py` renders one procedurally with numpy + zlib (PNG written by
hand to avoid a Pillow dependency) and is a decent template for code-generated
panoramas.

## Legacy: the Decker deck

The site used to be a [Decker](https://beyondloom.com/decker/) deck. That is no
longer being pursued (as of 2026-07-22), but the export is kept at `deck.html`
rather than deleted.

- `site.deck` / `index.deck` — the source decks, authored in the Decker app.
- `deck.html` — the exported deck, a single self-contained ~421KB file.
- `customize.py` — reapplies hand edits (the full-screen background image) that
  Decker's export would otherwise clobber. Now defaults to patching `deck.html`.

None of this is wired into the live site anymore. It can all be deleted whenever
— git history keeps it.

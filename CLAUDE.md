# scottmetoyer-web

A static personal site. No build system, no package manager, no server — just
files. Edit, commit, push; the host serves the folder as-is.

The site is a set of 360° **rooms** you look around in and travel between by
clicking hotspots painted into the space.

## Files

- `index.html`, `void.html`, `hall.html` — the rooms. Each is a short file that
  names its panorama and lists its exits; everything else comes from the two
  shared files below. `index.html` is the landing room.
- `pano.js` — the viewer engine: GL, interaction, hotspot projection, room
  transitions. Shared by every room.
- `pano.css` — all the styling. Shared by every room.
- `images/pano-*.png` — one panorama per room. Placeholders for now.
- `make_panos.py` — regenerates those placeholder panoramas.
- `deck.html`, `site.deck`, `index.deck`, `customize.py` — **legacy**, see below.

## Adding a room

Copy any room file and change three things: the `data-pano` image, the
`data-room` name, and the list of exits. No other file needs touching — styling
and behaviour come from `pano.css` / `pano.js` automatically.

```html
<body data-pano="images/pano-attic.png" data-room="The Attic" data-yaw="0" data-fov="80">
<nav id="hotspots">
  <a class="hotspot" href="index.html" data-yaw="120" data-pitch="4">The Plain</a>
</nav>
<script src="pano.js"></script>
```

`data-yaw` / `data-pitch` place an exit in the sphere, in degrees — yaw 0 is
straight ahead and increases to the right, pitch is above/below the horizon.
`data-yaw` / `data-pitch` / `data-fov` on `<body>` set where you are looking on
arrival. Rooms live at the top level so the relative paths stay simple.

Hotspots are real `<a>` elements projected to screen coordinates every frame,
which is why focus, cmd-click and hover all work normally. An exit that is
currently out of frame gets pinned to the edge of the screen, dimmed, with a
caret showing which way to turn — otherwise you can arrive facing away from
every exit and not know there is anywhere to go. Dragging that happens to start
on a hotspot is treated as a look, not a click.

## The viewer engine (`pano.js`)

It raycasts an equirectangular
(2:1) image in a fragment shader across a fullscreen triangle,
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

In `pano-hub.png` the cardinal posts are N=red, E=yellow, S=green, W=blue, so
a screenshot immediately shows whether orientation is right. Note that
`requestAnimationFrame` is throttled under headless virtual time, so the
on-screen readout won't update — screenshot the rendered frame instead of
scraping the DOM.

Navigation can be checked the same way: inject a script that clicks a hotspot,
then `--dump-dom` and read the `<title>` to see which room you ended up in.

## Panorama images

The viewer wants **equirectangular 2:1** images (what every 360 camera and
photosphere mode emits). 4096×2048 is a good working size.

Useful to remember when making them: the middle row is the horizon, the top and
bottom rows each collapse to a single point, the left and right edges must wrap,
and vertical lines in the world stay vertical columns in the image while every
other straight line becomes a sine curve.

`make_panos.py` renders the current placeholders procedurally with numpy + zlib
(PNG written by hand to avoid a Pillow dependency). Each room is one function
that takes a direction per pixel and returns a colour, so it doubles as a
template for code-generated panoramas. `./make_panos.py void` rebuilds one.

These are stand-ins. Real art goes in the same place — drop a 2:1 image in
`images/` and point a room's `data-pano` at it.

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

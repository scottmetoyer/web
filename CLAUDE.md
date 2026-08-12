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
  transitions, and the room editor. Shared by every room.
- `pano.css` — all the styling, viewer and editor. Shared by every room.
- `editor.html` — the room editor (see below). Not part of the site graph.
- `images/pano-*.png` — one panorama per room. Placeholders for now.
- `images/sprite-*.png` — transparent prop images (see Props below).
- `images/CREDITS.md` — where non-generated art came from, and its license.
- `make_panos.py` — regenerates those placeholder panoramas.
- `make_sprites.py` — regenerates the placeholder prop sprites.
- `add_prop.py` — finds real art and plants it in a room (see below).
- `deck.html`, `site.deck`, `index.deck`, `customize.py` — **legacy**, see below.

## The room editor (`editor.html`)

The fastest way to build and link rooms — no typing angles by hand.

1. Open `editor.html` (served over HTTP). **Drop images** — they all land in the
   tray at the top. **Right-click a tray tile → "set as background"** to make one
   the panorama; the rest stay as placeable props. (So you can place objects
   before committing to a background.)
2. Pick a tray image (or **+ exit**), then **right-click in the scene** to place
   it exactly where you aimed. Drag a placed item to move it; select it to edit
   its size, its **dialog HTML**, or an exit's label+target, or press <kbd>del</kbd>.
3. **Save room** downloads a ready-to-commit room `.html` (and hands back any
   images you dropped — move those into `images/`). The arrival view is set to
   wherever you're looking when you save.

A prop's dialog content is **raw HTML you author in the panel** — including
`<script>`, which runs when the dialog opens (`runScripts()` re-creates cloned
script nodes so they execute). It's your own content, so nothing is escaped;
that also means a broken tag there can break the dialog. "preview dialog" opens
it so you can check.

You can also edit an **existing** room in place by appending `?edit=1` to its
URL (e.g. `hall.html?edit=1`) — its props and exits become selectable, and
saving re-exports it.

The editor lives inside `pano.js`, gated on `?edit=1`, so it reuses the viewer's
exact projection — what you place is where visitors see it. `screenToAngles()`
is the inverse of the `placeProps`/`placeHotspots` projection; if you ever
change one, change the other, or right-click placement drifts from the render.

## Adding a room by hand

You rarely need this now that the editor exists, but the format is simple: copy
any room file and change three things — the `data-pano` image, the `data-room`
name, and the list of exits. No other file needs touching — styling and
behaviour come from `pano.css` / `pano.js` automatically.

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

## Props (clickable images that open a dialog)

A prop is an image planted in the scene — a figure on the plain, an object on a
plinth — that opens a modal dialog when clicked. Distinct from a hotspot: a
hotspot is a fixed-size wayfinding UI that navigates; a prop is a thing in the
world that scales with zoom and pops a dialog. Add one inside a room's `<body>`:

```html
<div id="props">
  <button class="prop" data-src="images/sprite-suit.png" data-alt="A man in a suit"
          data-yaw="24" data-pitch="-20" data-height="34">
    <template>
      <h2>Someone</h2>
      <p>Whatever the dialog should show — arbitrary HTML.</p>
    </template>
  </button>
</div>
```

- `data-yaw` / `data-pitch` aim at the prop's **anchor**, which defaults to its
  bottom-centre (the figure's feet) — so pitch is usually below the horizon for
  something standing on the ground. `data-anchor="center"` anchors by the middle
  instead.
- `data-height` is the prop's size in **degrees of view**, not pixels. That is
  what keeps it planted: zoom in and it grows with the scene, because its pixel
  height is `data-height / fov * viewportHeight` each frame.
- `data-src` is a transparent PNG, cropped tight to its alpha so the bottom edge
  really is the figure's feet. `make_sprites.py` generates placeholder sprites
  procedurally; real art goes in `images/` the same way (see `images/CREDITS.md`
  for where the non-generated sprites came from). The `<template>` holds the
  dialog content and is cloned into one shared native `<dialog>` on click.

Like hotspots, props are projected every frame and a drag that starts on one is
a look, not a click. Off-screen props are simply hidden (an object needs no
wayfinding). The dialog is a native `<dialog>` — Esc, backdrop-click and focus
trapping come for free, and focus returns to the prop on close. Without
JavaScript the buttons stay hidden rather than rendering broken.

## Populating the world (`add_prop.py`)

Putting a thing in a room means finding art you're allowed to use, cutting it
out cleanly, and writing the prop markup. This does all three:

    ./add_prop.py search "businessman" --preview     # → /tmp/prop-preview/*.png
    ./add_prop.py add oc:337378/young-indian-businessman --name suit \
        --room index.html --yaw 24 --pitch -20 --height 34 \
        --alt "A man in a suit" --title "Someone" --body "<p>Hello.</p>"

The source can be an openclipart id (`oc:337378`, optionally `oc:ID/slug`), a
`commons:File:Foo.svg`, any URL, or **a file on this machine** — same command
either way:

    ./add_prop.py add ~/Pictures/statue.jpg --name statue --yaw 90 --knockout-white

- **Search defaults to Openclipart because everything there is CC0**, so nothing
  we plant carries an attribution obligation. Commons is searchable too
  (`--source commons`) but most of its usable clipart is CC BY-SA, so the
  license is printed and non-free ones warn. Every add is logged to
  `images/CREDITS.md`; `--author` / `--license` override what gets recorded,
  which is how a local file gets honest provenance.
- `--preview` renders the candidates to PNGs so you can *look* before choosing.
  Worth doing — search text lies about what a piece actually looks like.
- **Cutout:** SVGs are rasterised with `rsvg-convert`, everything else through
  `sips` (so JPEG/PNG/TIFF/WebP all work). `--knockout-white` flood-fills the
  white background transparent *from the edges inward*, so an interior white —
  a shirt, the whites of eyes — survives. The result is always cropped to its
  alpha bounding box, because the prop anchors at bottom-centre: transparent
  padding under the feet would leave the thing hovering.
- **Re-running `add` with `--force` replaces the prop in place**, which is how
  you nudge yaw/pitch/height — but it overwrites hand-edited dialog HTML.
  Without `--force` it refuses rather than planting a duplicate.
- `--no-wire` just prints the snippet; `--body-file` reads dialog HTML from a
  file when it's more than one line.

For placing things by eye rather than by angle, the editor (`?edit=1`) is still
the better tool — this is for when you know roughly where it goes and want the
art fetched, cut out, credited and wired in one step.

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

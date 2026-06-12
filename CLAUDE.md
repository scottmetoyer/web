# scottmetoyer-web

A [Decker](https://beyondloom.com/decker/) deck published as a static website.

## Files

- `site.deck` — the source deck (authored in the Decker app). This is the source of truth for deck content.
- `index.html` — the **exported** deck (Decker "Export HTML"). A single self-contained file: the Decker runtime + the deck data embedded in a `<script language="decker">` block at the top. ~426KB, mostly machine-generated. Do not hand-author deck content here — edit it in Decker and re-export.
- `images/` — image assets referenced by hand edits (e.g. the page background).
- `customize.py` — post-export patch script (see below).

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

## Notes

- The deck is `locked:1` in the export.
- This is a static site — no build system, no package manager, no server.
  Just export, patch, and serve the files.

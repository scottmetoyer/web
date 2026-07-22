#!/usr/bin/env python3
"""Reapply post-export customizations to the Decker-exported deck.html.

LEGACY. The Decker deck is no longer the site — it lives on at deck.html and
this script only exists to keep that page working if it is ever re-exported.
Safe to delete along with deck.html / site.deck / index.deck.

Decker overwrites its export on every HTML export, wiping any hand edits.
Run this script after each export to put them back:

    ./customize.py            # patches ./deck.html in place
    ./customize.py path.html  # patches a different file

Each entry in PATCHES is an exact string replacement. The script is
idempotent: if a patch is already applied it is skipped, and if neither the
"before" nor "after" text is found it warns you (usually a sign Decker
changed its export format and the anchor needs updating).

To add a new tweak: copy an existing Patch(...) block, set `before` to the
exact text Decker emits and `after` to what you want instead.
"""

import sys
from dataclasses import dataclass


@dataclass
class Patch:
    name: str
    before: str
    after: str


# ---------------------------------------------------------------------------
# Customizations — add new ones here.
# ---------------------------------------------------------------------------
PATCHES = [
    Patch(
        name="full-screen background image",
        before="body{background:black;margin:0;display:flex;align-items:center;justify-content:space-between;-webkit-user-select:none;user-select:none;}",
        after="body{background:#000 url('images/abc_cover_notext_variant.jpg') center/cover no-repeat fixed;margin:0;display:flex;align-items:center;justify-content:space-between;-webkit-user-select:none;user-select:none;}",
    ),
]
# ---------------------------------------------------------------------------


def main(path: str) -> int:
    try:
        with open(path, "r", encoding="utf-8") as f:
            html = f.read()
    except FileNotFoundError:
        print(f"error: {path} not found", file=sys.stderr)
        return 1

    changed = False
    problems = 0
    for p in PATCHES:
        if p.after in html:
            print(f"  ok    already applied: {p.name}")
        elif p.before in html:
            html = html.replace(p.before, p.after)
            changed = True
            print(f"  +     applied:         {p.name}")
        else:
            problems += 1
            print(f"  WARN  anchor not found: {p.name} "
                  f"(Decker export format may have changed)")

    if changed:
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"\nwrote {path}")
    else:
        print(f"\nno changes needed for {path}")

    return 1 if problems else 0


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "deck.html"
    sys.exit(main(target))

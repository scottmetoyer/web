# Image credits

Where the art in this folder came from. Generated placeholders (`make_panos.py`,
`make_sprites.py`) are not listed — they are ours.

## `sprite-suit.png`

"young indian businessman", by *Aryan001* — https://openclipart.org/detail/337378/young-indian-businessman

Public domain (CC0 1.0). Everything on Openclipart is released under CC0, so no
attribution is required; this note is for our own bookkeeping.

Processed for use as a prop: rendered from the source SVG at 1200px tall
(`rsvg-convert -h 1200`), then cropped to its alpha bounding box → 332×1172, so
the bottom edge is the figure's feet and the prop anchor lands on the ground.

## `sprite-snake-mountain.webp`

Product photograph of the Icon Heroes *Snake Mountain* statue (Masters of the
Universe) — https://www.iconheroes.com/, source image `6345568_orig.jpg`.

**Not a free license.** The photo is Icon Heroes'; the design is Mattel's. It is
in here as placeholder art the way the procedural panoramas are — fine while
this is a personal sketch, but it is not cleared for redistribution, so swap it
before treating the north landmark as finished.

Background knocked out (white flood-fill, tolerance 20) and cropped to alpha →
795×800, the photo's native size. Encoded `cwebp -q 90 -alpha_q 100`: 156KB,
against 926KB as a PNG, which matters because this one is served to visitors.

Stands due north in `index.html` as a scenery prop (a `.prop` with no
`<template>`, so it is part of the view rather than something you click). It was
briefly baked into `pano-hub.png` instead — that capped it at 170px and looked
like mush the moment you zoomed.

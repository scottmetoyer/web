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

"6345568_orig.jpg", by *Icon Heroes (product photo); design Mattel* — https://www.iconheroes.com/cdn/shop/products/6345568_orig.jpg

License: NOT free — placeholder art, not cleared for redistribution

Rendered 800px tall, denoised (3×3 median), cropped to its alpha bounding box (795×800) so the bottom edge is the sprite's anchor point, encoded WebP q90 (98KB).

Rebuild it with exactly that:

    ./add_prop.py cutout https://www.iconheroes.com/cdn/shop/products/6345568_orig.jpg \
        --name snake-mountain --px 800 --knockout-white 20 --denoise --webp 90 --force

The photo is Icon Heroes'; the design is Mattel's. It is here as placeholder art
the way the procedural panoramas are — fine while this is a personal sketch, not
cleared for redistribution, so swap it before the north landmark counts as
finished.

**800px is the ceiling.** That is the largest this photo exists at anywhere —
the CDN returns the same file for any `?width=`, and the review galleries are
800×450 shots on real backgrounds that can't be cut out cleanly. So the sprite
gets magnified about 2× on a retina screen at 32° fov, which is why it is
denoised: the source carries its own JPEG mottle and magnifying it magnifies the
speckle too. The median drops that ~60% in the rendered frame while costing ~4%
edge strength at the default zoom, where the two are indistinguishable.

Stands due north in `index.html` as a scenery prop (a `.prop` with no
`<template>`, so it is part of the view rather than something you click). It was
briefly baked into `pano-hub.png` instead — that capped it at 170px and looked
like mush the moment you zoomed.

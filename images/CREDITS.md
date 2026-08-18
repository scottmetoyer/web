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

## `sprite-pc.webp`

"Desktop Computer (#10)", by *oksmith* — https://openclipart.org/detail/325360/desktopcomputer

License: Public domain (CC0 1.0)

Rendered 1200px tall, cropped to its alpha bounding box (1155×1200) so the bottom edge is the sprite's anchor point, encoded WebP lossless (25KB).

## `sprite-pc-glitch.webp`

"Purple Flower with smile", by *barnheartowl* — https://openclipart.org/detail/236026/purple-daisy-with-face

License: Public domain (CC0 1.0)

"Sunflower", by *ihalseide* — https://openclipart.org/detail/283964/1501448000

License: Public domain (CC0 1.0)

"Sunflower kaleidoscope 27", by *Firkin* — https://openclipart.org/detail/259268/SunflowerKaleidoscope27

License: Public domain (CC0 1.0)

"Tulip", by *Eggib* — https://openclipart.org/detail/320554/tulpan2

License: Public domain (CC0 1.0)

"Tulip", by *Eggib* — https://openclipart.org/detail/320163/tulpan

License: Public domain (CC0 1.0)

"Red Flower", by *keriann3* — https://openclipart.org/detail/219765/Red-Flower-2015053159

License: Public domain (CC0 1.0)

"flower art svg", by *metashoip* — https://openclipart.org/detail/351216/flower-art-line-ffff

License: Public domain (CC0 1.0)

Fragments of the above, cut as rotated rect/tri/wedge/shear sections and layered over `sprite-pc.webp` by `glitch_sprite.py --seed 5 --fragments 26`. Same dimensions as the base, so the prop's anchor is unchanged.

## `sprite-snake-mountain-glitch.webp`

"Bodybuilder", by *liftarn* — https://openclipart.org/detail/322890/bodybuilder-in-thong

License: Public domain (CC0 1.0)

"Muscle Man Cartoon - Colour Remix", by *j4p4n* — https://openclipart.org/detail/341081/muscle-man-cartooncolour

License: Public domain (CC0 1.0)

"Faceless bodybuilder", by *liftarn* — https://openclipart.org/detail/322891/faceless-bodybuilder

License: Public domain (CC0 1.0)

"Bodybuilder", by *j4p4n* — https://openclipart.org/detail/332459/bodybuilder-pd

License: Public domain (CC0 1.0)

"Bodybuilder woman", by *liftarn* — https://openclipart.org/detail/341337/bodybuilder-woman

License: Public domain (CC0 1.0)

Fragments of the above, cut as rotated rect/tri/wedge/shear sections and layered over `sprite-snake-mountain.webp` by `glitch_sprite.py --seed 9 --fragments 28 --region limbs`. Same dimensions as the base, so the prop's anchor is unchanged.

## `sprite-suit-glitch.webp`

"dogface butterfly", by *jbruce* — https://openclipart.org/detail/239649/dogface-butterfly

License: Public domain (CC0 1.0)

"Wasp", by *oksmith* — https://openclipart.org/detail/316155/1551633495

License: Public domain (CC0 1.0)

"Lady Beetle - Colour Remix", by *j4p4n* — https://openclipart.org/detail/332748/lady-beetle-colour

License: Public domain (CC0 1.0)

"Spider 2", by *Firkin* — https://openclipart.org/detail/264582/Spider2

License: Public domain (CC0 1.0)

"Stag Beetle", by *j4p4n* — https://openclipart.org/detail/306625/1536852963

License: Public domain (CC0 1.0)

"ant - coloured", by *frankes* — https://openclipart.org/detail/214039/ameise

License: Public domain (CC0 1.0)

"Paper Wasp", by *algotruneman* — https://openclipart.org/detail/289379/wasp-paper

License: Public domain (CC0 1.0)

Fragments of the above, cut as rotated rect/tri/wedge/shear sections and layered over `sprite-suit.png` by `glitch_sprite.py --seed 11 --fragments 26`. Same dimensions as the base, so the prop's anchor is unchanged.

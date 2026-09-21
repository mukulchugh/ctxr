# ctxr brand assets

A video frame opens into text lines. The play triangle keeps the video origin visible at small sizes.

| File | Dimensions (px unless noted) | Bytes | Use |
| --- | --- | ---: | --- |
| [logo.svg](logo.svg) | 304 × 96 viewBox | 1,331 | Primary mark + outlined wordmark; transparent |
| [logo-mark.svg](logo-mark.svg) | 96 × 96 viewBox | 361 | Mark only; transparent |
| [logo-512.png](logo-512.png) | 512 × 162 | 7,977 | Primary logo; transparent |
| [logo-1024.png](logo-1024.png) | 1024 × 323 | 16,606 | Primary logo; transparent |
| [logo-mark-512.png](logo-mark-512.png) | 512 × 512 | 3,552 | Mark only; transparent |
| [logo-mark-1024.png](logo-mark-1024.png) | 1024 × 1024 | 8,643 | Mark only; transparent |
| [social-preview.png](social-preview.png) | 1280 × 640 | 606,647 | GitHub social preview; light background |
| [banner.png](banner.png) | 1600 × 400 | 459,544 | README banner; dark background |
| [icon.png](icon.png) | 512 × 512 | 3,522 | App icon; transparent mark |
| [favicon.ico](favicon.ico) | 16, 24, 32, 48, 64, 128, 256 square | 10,519 | Multi-resolution favicon; transparent |
| [FONT-LICENSE.txt](FONT-LICENSE.txt) | Text | 4,495 | Space Grotesk SIL Open Font License 1.1 |
| [README.md](README.md) | Text | — | This asset guide |

## Palette

- Context blue: `#4878E8` for the logo and accents.
- Ink: `#111B27` for text and dark backgrounds.
- Paper: `#F4F1E9` for light backgrounds and reversed text.

These are the three base colors. Raster artwork includes edge smoothing and slight tonal variations. Use the SVGs for exact-color reproduction. The blue logo works on both light and dark backgrounds without swapping files.

## Typography and reuse

The wordmark uses **Space Grotesk Bold (700)**, converted to vector paths so it needs no installed font. [Space Grotesk](https://github.com/floriankarsten/space-grotesk) is licensed under SIL OFL 1.1; see `FONT-LICENSE.txt`. Raster lettering is baked into the PNGs; Space Grotesk is the reference font for future layouts, rather than an editable font embedded in those images.

The mark is original vector geometry. Artwork is covered by the repository's MIT license; the font retains its OFL license. No stock icons are used.

Use the mark at 32 px and above, and the full logo at 32 px high and above. Use the ICO for smaller favicon slots. Keep the SVG aspect ratio and leave clear space around the mark. Logo PNG filenames specify width; mark PNGs are square. All SVGs are self-contained paths and geometry, with no linked images or fonts.

The frame and narration in the social card and banner are illustrative walkthrough samples. The README already references `banner.png`. Upload `social-preview.png` in the repository's social preview settings to use it for shared links.

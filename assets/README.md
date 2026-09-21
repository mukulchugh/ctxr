# ctxr brand assets

A video frame opens along a diagonal cut into three text strokes. That cut passes through the custom x and divides the compositions, connecting the small mark to the full identity.

## Palette

| Color | Hex | Use |
| --- | --- | --- |
| Persimmon | `#C65336` | Mark, standalone lockup and small accents |
| Ink | `#242722` | Text on paper; dark fields |
| Paper | `#F4EEDF` | Light fields; text on ink |

The same colors appear in both layouts. Ink/paper contrast is 13.07:1. Persimmon is 3.87:1 against paper and 3.38:1 against ink: use it for marks and large graphics, not small body text. SVGs use exact colors; rasters add antialiased edge colors.

## Typography

**Azeret Mono**, weights 400, 500 and 600, by the Azeret Project Authors, is licensed under the **SIL Open Font License 1.1**. The unmodified variable font is included at [source/AzeretMono.ttf](source/AzeretMono.ttf); its license is [FONT-LICENSE.txt](FONT-LICENSE.txt). Source: [Google Fonts' Azeret Mono distribution](https://github.com/google/fonts/tree/main/ofl/azeretmono), upstream [Displaay / Azeret](https://github.com/displaay/azeret).

The wordmark uses the 600 weight for c, t and r, with optical advances in place of fixed character spacing. Its x is original vector geometry: one continuous diagonal passes between two separated strokes. All lettering in every SVG is outlined to paths; no font installation or external resource is needed to display the artwork. The bundled font is unmodified; the custom x exists only in the artwork.

## Files and production

| File | Size | How it was made / use |
| --- | --- | --- |
| [logo.svg](logo.svg) | 360 × 96 | Original cut-frame geometry and outlined custom wordmark; transparent, single-color persimmon |
| [logo-mark.svg](logo-mark.svg) | 96 × 96 | Original vector mark; transparent |
| [logo-512.png](logo-512.png) | 512 × 137 | Local CairoSVG export of the lockup |
| [logo-1024.png](logo-1024.png) | 1024 × 273 | Local CairoSVG export of the lockup |
| [logo-mark-512.png](logo-mark-512.png) | 512 × 512 | Local CairoSVG export of the mark |
| [logo-mark-1024.png](logo-mark-1024.png) | 1024 × 1024 | Local CairoSVG export of the mark |
| [social-preview.png](social-preview.png) | 1280 × 640 | Locally drawn, outlined SVG composition rasterized with CairoSVG |
| [banner.png](banner.png) | 1600 × 400 | Wide composition of the same system, rasterized with CairoSVG |
| [icon.png](icon.png) | 512 × 512 | Mark on an opaque paper ground, locally rasterized for dependable display on arbitrary backgrounds |
| [favicon.ico](favicon.ico) | 16, 24, 32, 48, 64, 128, 256 | Seven embedded sizes, encoded locally with Pillow from the icon |
| [source/social-preview.svg](source/social-preview.svg), [source/banner.svg](source/banner.svg) | Native export sizes | Self-contained vector masters, including every outlined text element |
| [source/walkthrough.md](source/walkthrough.md) | Markdown | Example emitted by the actual `ctxr.cli.render` function using a synthetic fixture |
| [source/frames/0005_00m32s.jpg](source/frames/0005_00m32s.jpg) | 1280 × 608 | Locally rendered Markdown specimen for the illustrative walkthrough's image reference |
| [generate.py](generate.py) | Python | Reproducible geometry, typesetting, rasterization and export checks |
| [CRITIQUE.md](CRITIQUE.md) | Markdown | Critique of the first identity, written before this redesign |

## Walkthrough provenance

The card and banner show an excerpt of **ctxr's own Markdown output**, not a third-party application or a film still. The heading, timestamp/watch syntax, image reference and narration come from the actual renderer; the specimen omits the explanatory paragraph between the walkthrough heading and the first section. Only typography and line wrapping change.

This is an **illustrative self-demo**, labeled in both images. `00:32` is a fixture timestamp, `VIDEOID` is a neutral placeholder, and “The folder is the state; there is no database.” is taken verbatim from [docs/MCP.md](../docs/MCP.md). It is not presented as narration recovered from a real recording. The example frame is a locally rendered Markdown specimen, not a captured video frame. No third-party screenshots, film assets, stock icons or textures are used.

## Reproduce

The exports were produced with CairoSVG 2.9.1, fontTools 4.65.0 and Pillow 12.3.0 in a uv virtual environment. These are artwork tools, not ctxr runtime dependencies. Cairo must be installed locally.

```sh
uv venv /tmp/ctxr-brand-venv
uv pip install --python /tmp/ctxr-brand-venv/bin/python cairosvg==2.9.1 fonttools==4.65.0 pillow==12.3.0
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib /tmp/ctxr-brand-venv/bin/python assets/generate.py
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib /tmp/ctxr-brand-venv/bin/python assets/generate.py --check
```

The environment prefix above locates Homebrew Cairo on Apple Silicon. Omit it where Cairo is already on the library search path. Generation runs entirely locally and does not download videos. Font outlines use [fontTools SVGPathPen](https://fonttools.readthedocs.io/en/latest/pens/svgPathPen.html); raster exports use [CairoSVG](https://cairosvg.org/documentation/).

## Use and limits

Use the mark at 32 px and above; use the paper-backed ICO for favicon slots. Leave at least one mark stroke of clear space. Preserve the lockup's proportions: PNG filenames specify width, not a square canvas. SVG fills can be changed to ink on light backgrounds or paper on dark backgrounds for monochrome use.

Both compositions keep the name and tagline primary. The Markdown excerpt is detail for larger displays and cannot remain fully readable when the 1600 px banner is reduced to a narrow phone width. README.md repeats the tagline as selectable text.

The original artwork follows the repository's MIT license; the font retains its OFL license. README.md already references `banner.png`. `social-preview.png` is ready to upload in the repository's social preview settings; no upload is performed by the generator.

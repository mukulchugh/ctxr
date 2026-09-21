# Brand assets

ctxr uses a wordmark-only logo. Preserve the custom split x; do not add a separate symbol.

## Colors and type

| Color | Hex | Use |
| --- | --- | --- |
| Carbon | `#151714` | Dark backgrounds and text on light surfaces |
| Chalk | `#F5F7F2` | Light backgrounds and text on dark surfaces |
| Citron | `#C4F25A` | Wordmark on dark surfaces, timestamp and app icon |

Use carbon text on citron. Do not use citron for small text on chalk. The video frame retains its original colors.

The wordmark uses **Azeret Mono 650**, optical spacing and a custom cut through the x. Supporting copy uses weights 400 and 500. Every SVG letter is outlined, so the artwork needs no installed font. The unchanged [font](source/AzeretMono.ttf) is from [Displaay / Azeret](https://github.com/displaay/Azeret), under [SIL OFL 1.1](FONT-LICENSE.txt).

## Files

| Asset | Vector | Raster |
| --- | --- | --- |
| Carbon wordmark | [logo.svg](logo.svg) | [512 px](logo-512.png), [1024 px](logo-1024.png) |
| Chalk wordmark | [logo-dark.svg](logo-dark.svg) | [512 px](logo-dark-512.png), [1024 px](logo-dark-1024.png) |
| Citron wordmark | [logo-accent.svg](logo-accent.svg) | [512 px](logo-accent-512.png), [1024 px](logo-accent-1024.png) |
| Dark README banner | [banner.svg](banner.svg) | [banner.png](banner.png), 1600 × 400 |
| Light README banner | [banner-light.svg](banner-light.svg) | [banner-light.png](banner-light.png), 1600 × 400 |
| Dark social preview | [social-preview.svg](social-preview.svg) | [social-preview.png](social-preview.png), 1280 × 640 |
| Light social preview | [social-preview-light.svg](social-preview-light.svg) | [social-preview-light.png](social-preview-light.png), 1280 × 640 |
| App icon | [icon.svg](icon.svg) | [icon.png](icon.png), 512 × 512 |
| Favicon | [favicon.svg](favicon.svg) | [32 px PNG](favicon.png), [multi-size ICO](favicon.ico) |

The README switches banners with the reader's color scheme. GitHub's repository social-preview setting uses `social-preview.png`; changing the file alone does not update that setting. Upload it under Settings → General → Social preview.

Use the wordmark at least 80 px wide outside favicon slots. The full wordmark is retained in favicons; prefer 32 px where supported. Keep its aspect ratio and surrounding clear space.

## Authentic sample and rights

The card and banner contain a real frame from the [original Rickroll video](https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=100), extracted by ctxr at 100.04 seconds and displayed as `01:40`. The five-word lyric excerpt begins at 102.12 seconds and is assigned to that frame by ctxr's unchanged alignment function. The frame was selected with the default scene-change threshold and interval. See [sample metadata](source/sample.json) and [original extracted JPEG](source/frame.jpg).

YouTube captions were rate-limited for this extraction. Local transcription used the small Whisper model with speech detection disabled for the music excerpt. The compositions change typography and clip only the black pillarboxes; the video picture is not synthesized or retouched. SVGs embed the JPEG directly.

Original identity geometry and compositions use the repository's MIT license. The font keeps its OFL license. The Rick Astley frame and lyric remain third-party material and are excluded from the MIT grant; no open license or endorsement is claimed for them.

## Reproduce and check

Artwork dependencies are separate from ctxr runtime dependencies. Install Cairo locally, then:

```sh
uv venv /tmp/ctxr-brand-venv
uv pip install --python /tmp/ctxr-brand-venv/bin/python cairosvg==2.9.1 fonttools==4.65.0 pillow==12.3.0
/tmp/ctxr-brand-venv/bin/python assets/generate.py
/tmp/ctxr-brand-venv/bin/python assets/check.py
```

On Apple Silicon, prefix the generator command with `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` if Cairo is not on the library search path. Generation is local and uses the bundled font and frame; it does not download video or call a model.

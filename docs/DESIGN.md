---
name: ctxr
description: Context from video, for agents.
colors:
  persimmon: "#C65336"
  ink: "#242722"
  paper: "#F4EEDF"
typography:
  wordmark:
    fontFamily: "Azeret Mono"
    fontWeight: 600
  tagline:
    fontFamily: "Azeret Mono"
    fontWeight: 500
  specimen:
    fontFamily: "Azeret Mono"
    fontWeight: 400
---

# Design System: ctxr

## Overview

**Creative North Star: "The frame becomes text."** A cut video frame opens into three text strokes. The diagonal continues through the custom x and the static compositions. The identity is precise, flat and typographic.

This record covers static GitHub brand artwork. The [full asset reference](assets/README.md) owns usage, export inventory, licensing and reproduction; [assets/generate.py](assets/generate.py) contains the implemented geometry and typesetting.

## Colors

Persimmon is the primary accent for the mark, standalone lockup and small graphic details. Ink and paper form the neutral fields and reading colors. Ink/paper contrast is 13.07:1; persimmon against either neutral falls below 4.5:1, so reserve it for marks and large graphics rather than small body text.

## Typography

Azeret Mono supplies the lettering at the weights above; specimen headings also use 500 and 600. The wordmark has optical advances and an original vector x, so typing the name in the font does not recreate the logo. SVG lettering is outlined and self-contained. The bundled unmodified font retains its SIL OFL license.

## Layout

The social preview is 1280 × 640; the banner is 1600 × 400. Both divide paper identity and ink walkthrough fields along the mark's diagonal, with the name and tagline primary. These are fixed compositions: fine specimen text is not expected to stay readable at narrow display widths. Keep the tagline as selectable text in the README.

## Elevation & Depth

Flat color fields and negative space carry the hierarchy. The implemented artwork uses no shadows or gradients.

## Shapes

The angular cut-frame mark shares its diagonal with the custom x. Preserve supplied geometry and lockup proportions. Leave at least one mark stroke of clear space; use the mark at 32 px and above, and the paper-backed ICO for favicon slots.

## Components

The system consists of the cut-frame mark, custom wordmark/lockup and illustrative Markdown walkthrough specimen. Reuse the exported assets. The specimen's timestamp, watch link, frame reference and narration come from the product renderer; its fixture content remains labeled illustrative.

## Do's and Don'ts

- Do use ink on light backgrounds or paper on dark backgrounds for monochrome logo variants.
- Do preserve the custom x and outlined lettering.
- Do keep fixture provenance visible when using the illustrative walkthrough.
- Don't stretch the lockup into a square or use persimmon for small body text.
- Don't infer application controls, interaction states or responsive breakpoints from this static artwork.

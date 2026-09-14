---
version: alpha
name: Vodafone
description: Monumental uppercase display. Vodafone-red chapter bands.
colors:
  primary: "#0D0D0D"
  secondary: "#6D6D6D"
  tertiary: "#E60000"
  neutral: "#F4F4F4"
  surface: "#FFFFFF"
  on-primary: "#FFFFFF"
typography:
  display:
    fontFamily: Archivo Black
    fontSize: 6rem
    fontWeight: 900
    letterSpacing: "-0.025em"
  h1:
    fontFamily: Archivo Black
    fontSize: 2.8rem
    fontWeight: 900
  body:
    fontFamily: Inter
    fontSize: 1rem
    lineHeight: 1.6
  label:
    fontFamily: Inter
    fontSize: 0.74rem
    fontWeight: 700
    letterSpacing: "0.1em"
rounded:
  sm: 2px
  md: 4px
  lg: 6px
spacing:
  sm: 8px
  md: 16px
  lg: 32px
components:
  button-primary:
    backgroundColor: "{colors.tertiary}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.md}"
    padding: 12px 20px
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.primary}"
    rounded: "{rounded.lg}"
    padding: 24px
---
## Overview

Vodafone: monumental all-caps display, saturated red chapter bands on white, uncompromising sans.

## Colors

The palette is built around high-contrast neutrals and a single accent that drives interaction.

- **Primary (`#0D0D0D`):** Headlines and core text.
- **Secondary (`#6D6D6D`):** Borders, captions, and metadata.
- **Tertiary (`#E60000`):** The sole driver for interaction. Reserve it.
- **Neutral (`#F4F4F4`):** The page foundation.

## Typography

- **display:** Archivo Black 6rem
- **h1:** Archivo Black 2.8rem
- **body:** Inter 1rem
- **label:** Inter 0.74rem

## Do's and Don'ts

- **Do** use Tertiary for exactly one action per screen.
- **Do** let Neutral carry the composition — negative space is a feature.
- **Don't** introduce gradients. This system is flat on purpose.
- **Don't** mix Tertiary with alternate accents; the single-accent rule is load-bearing.

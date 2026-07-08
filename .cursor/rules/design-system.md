# Design System Rules

> Last updated: 2026-06-28

## Palette

- **Primary color: soft terracotta `#E07A5F`** — chosen as the main brand color for buttons, links and active states. Decided 2026-06-10 after the "light palette" refresh.
- Background: light beige `#F8F5F1` — clean, neutral backdrop.
- Accent: dusty rose / plum `#BE95C4` for interactive highlights.
- Design tokens live in `src/index.css` and `tailwind.config.ts` (`--radius`, `boxShadow.card`). Do not hardcode hex values in components.

## Do / Don't

- DO use gentle shadows (`boxShadow.card`) and rounded corners.
- DON'T reintroduce heavy "stamped" shadows or `font-extrabold` on headlines — this was explicitly removed in the 2026-06-10 design refresh and must not come back.
- DO keep the palette "light": softer terracotta/plum, no saturated reds.

## Typography

- Headline font: Belleza (humanist sans-serif).
- Body font: Alegreya (humanist serif) for long recipe instructions — readability first.
- Hebrew text must render with proper Hebrew glyph support; test both fonts with niqqud-free Hebrew.

## Components

- shadcn/ui primitives only, regenerated via CLI. Never hand-edit files under `src/components/ui/`.
- List item components must be wrapped in `React.memo`.

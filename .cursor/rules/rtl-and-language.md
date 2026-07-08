# RTL & Language Rules

> Last updated: 2026-07-01

## RTL — mandatory

- The entire UI is **RTL-first**. `<html dir="rtl" lang="he">` is set at the root.
- **Always use logical properties**: `ms-*`/`me-*`, `ps-*`/`pe-*`, `start`/`end`. **Never** `left`/`right`, `ml-*`/`mr-*`, `pl-*`/`pr-*`.
- Icons that imply direction (arrows, chevrons) must flip in RTL — use `rtl:rotate-180` or logical variants.
- Exception: code snippets, API paths and URLs stay LTR (`dir="ltr"` on those spans).

## Language policy

- **UI text is Hebrew only.** Code, identifiers, commit messages and API routes are English.
- History: migration `009` introduced bilingual `*_he` / `*_en` columns for a planned English translation. On **2026-06-20 the decision was reversed** — the app is Hebrew-only, and migration `012_hebrew_only.sql` folded the bilingual columns back into the plain columns and dropped them.
- **Decision (final): the interface is not translated to any language other than Hebrew.** Do not reintroduce per-language columns or an i18n framework.
- Brand strings (title, header, PWA manifest, login screen) are Hebrew. Infrastructure identifiers (`wrangler.toml name`, `package.json name`, D1 database name, R2 bucket name) stay in English — they are infrastructure IDs, never rename them.

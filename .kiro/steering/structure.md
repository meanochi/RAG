# Project Structure Steering

> Observed: 2026-06-15

## Layout

- `src/` — React frontend. Contexts in `src/contexts/`, shared libs in `src/lib/`,
  shadcn/ui primitives in `src/components/ui/` (CLI-generated, never hand-edited).
- `functions/` — Cloudflare Pages Functions (the API). Zod schemas in
  `functions/validation/schemas.ts`, helpers in `functions/utils/`.
- `migrations/` — D1 SQL migrations, `NNN_description.sql`, applied via `scripts/migrate.mjs`.
- `public/` — static assets: PWA manifest, icons, service worker, `_headers` (CSP).

## Conventions that MUST be followed

- `src/lib/db.ts` is **server-only** — never import it from client code.
- Recipe images render only through `<RecipeImage>` (`src/lib/image.ts` helpers).
  A raw `<img src={recipe.imageUrl}>` is a review-blocking violation.
- Errors: `logError(scope, err, ctx?)` from `functions/utils/log.ts`.
  `console.error(err)` is forbidden (leaks stack traces).
- All API error paths return via `errorResponse()` from `functions/utils/response.ts`.
- IDs via `generateId()` in `src/lib/utils.ts`. Imports use the `@/` alias.
- New pages must be lazy-imported in `src/router.tsx` and weighed against the JS budget.

## Migration workflow

1. One file per change: `migrations/NNN_short_description.sql` (zero-padded, snake_case).
2. Never edit an applied migration — add a new one to amend.
3. Apply with `npm run db:migrate:apply:local` and `:remote`; the `migrations` table
   tracks what ran.

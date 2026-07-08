# מתכונים לופיאנסקי — Project Guide

Hebrew-only (RTL) recipe management PWA with full CRUD, meal planning, shopping lists, offline support with sync, and AI-powered recipe parsing/import. Built as a Cloudflare Pages app with D1 SQLite, R2 image storage, and Cloudflare AI.

## URLs

| Purpose | URL |
|---------|-----|
| Production | `https://matkonim.lopiansky.org` |
| Pages fallback | `https://cookbook-lopiansky.pages.dev` |
| R2 public bucket | `https://pub-4d4272c26e674f138f72a4c8d5705e38.r2.dev` (`cookbook-images`) |

> **Internal identifiers stay in English.** Brand strings (title, header, manifest, login) are Hebrew. Don't rename `wrangler.toml name`, `package.json name`, `database_name`, R2 bucket name — they're infrastructure IDs.

## Tech Stack

- **Frontend:** React 18.3, TypeScript 5, Vite 6, Tailwind CSS 3.4, shadcn/ui (Radix UI)
- **Backend:** Cloudflare Pages Functions (Workers runtime)
- **Database:** Cloudflare D1 (SQLite)
- **Object storage:** Cloudflare R2 (`cookbook-images` bucket, public dev URL above)
- **AI:** Cloudflare AI (Llama 3.1 70B) for recipe text parsing
- **Forms:** react-hook-form + Zod validation
- **Routing:** React Router v7
- **Cloudflare plan:** **Free** — Image Resizing (`/cdn-cgi/image/`) is **not** available; we pre-resize images with sharp and upload variants to R2 (see "Image guidelines").

## Architecture map

```
├── src/                      React frontend
│   ├── App.tsx               Root layout (AuthGate + Suspense)
│   ├── router.tsx            Routes (lazy-loaded pages)
│   ├── pages/                HomePage, LoginPage, etc.
│   ├── components/
│   │   ├── ui/               shadcn/ui primitives — regenerate via CLI, never edit by hand
│   │   ├── layout/           Header, Footer
│   │   ├── OfflineSync.tsx   Offline banner + outbox flusher
│   │   └── recipes/          RecipeCard, RecipeDetail, RecipeForm, RecipeImage (Phase 4)
│   ├── contexts/             AuthContext, RecipeContext, ShoppingListContext, AppProviders
│   ├── hooks/                useDebounce, use-toast, use-mobile
│   ├── lib/
│   │   ├── auth.ts           PBKDF2 hashing, session utils
│   │   ├── db.ts             SERVER-ONLY D1 query functions (imported by functions/)
│   │   ├── image.ts          getImageUrl / getSrcSet / getDefaultImage — single source of truth for image URLs
│   │   ├── fractions.ts      parseAmount / formatAmount — fraction amounts (½, 1/3, 1 1/2)
│   │   ├── ingredientParser.ts  Local Hebrew "2 כוסות קמח" → {amount, unit, name, notes} parser
│   │   ├── units.ts          normalizeUnit / shoppingItemKey — shared client+server unit merging
│   │   ├── offlineQueue.ts   IndexedDB outbox for offline mutations, replayed on reconnect
│   │   └── utils.ts          generateId, getDisplayUnit, cn
│   └── types/index.ts        Recipe, Ingredient, etc.
├── functions/                Cloudflare Pages Functions (API)
│   ├── api/
│   │   ├── _middleware.ts    Auth + CSRF middleware
│   │   ├── auth/             login, logout, me
│   │   ├── recipes/          CRUD + search
│   │   ├── shopping-list.ts
│   │   ├── meal-plans/
│   │   ├── admin/users/      Admin only
│   │   └── ai/               parse-recipe.ts (text → recipe), import-recipe.ts (URL → recipe)
│   ├── validation/schemas.ts Zod schemas
│   ├── utils/
│   │   ├── response.ts       jsonResponse, errorResponse
│   │   └── log.ts            logError — never log raw errors
│   └── types.ts
├── migrations/               D1 SQL migrations (NNN_description.sql)
├── public/                   Static assets (manifest, icons, sw, _headers)
├── scripts/
│   ├── migrate.mjs           Apply pending D1 migrations (uses `migrations` table)
│   └── import-data/          One-shot data import helpers
└── wrangler.toml
```

Data flow: `D1 → src/lib/db.ts → functions/api/* → fetch() → src/contexts/* → components`. Recipe images flow `R2 → <RecipeImage> → <img>`.

## Performance budgets

These are enforced via PR review. If a change pushes past a budget, justify in the PR description.

| Metric | Budget |
|--------|--------|
| LCP (mobile, simulated 4G) | < 2.5s |
| `/api/recipes` p95 | < 200ms |
| Main JS chunk (gzip) | < 200KB |
| Image weight per card | < 50KB |
| Initial transferred bytes | < 200KB |

## API contract

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/auth/login | Public | Login (email + password). Rate-limited 5/min/IP. |
| POST | /api/auth/logout | Yes | Logout |
| GET | /api/auth/me | Yes | Current user |
| GET | /api/recipes | Yes | List recipes — Phase 2 will paginate (`?limit=&cursor=`, summaries only). |
| POST | /api/recipes | Editor+ | Create recipe |
| GET | /api/recipes/:id | Yes | Get full recipe |
| PUT | /api/recipes/:id | Editor+ | Update recipe |
| DELETE | /api/recipes/:id | Editor+ | Delete recipe |
| GET | /api/recipes/search?q= | Yes | Search recipes (FTS5, Hebrew) |
| GET | /api/recipes/by-slug/:slug | Yes | Get full recipe by slug (deep link) |
| GET | /api/autocomplete/tags?q=&limit= | Yes | Tag suggestions from existing recipes |
| GET | /api/autocomplete/ingredients?q=&limit= | Yes | Ingredient name suggestions |
| GET | /api/autocomplete/sources?q=&limit= | Yes | Source suggestions |
| GET/POST/DELETE/PATCH | /api/shopping-list | Yes | Shopping list CRUD — one shared household list, not per-user |
| GET/POST | /api/meal-plans | Yes | Meal plans — shared household plans, not per-user |
| PUT/DELETE | /api/meal-plans/:id | Yes | Update/delete meal plan (any authenticated user, not just the creator) |
| GET/POST/PUT/DELETE | /api/admin/users | Admin | User management |
| POST | /api/ai/parse-recipe | Yes | AI recipe parsing from pasted text (≤20K chars). Rate-limited 10/min/IP. |
| POST | /api/ai/import-recipe | Yes | Import recipe from a website URL: server fetches page (JSON-LD Recipe preferred, HTML-to-text fallback) → AI parse → validated recipe + `sourceUrl`. Rate-limited 10/min/IP. |
| POST | /api/uploads/recipe-image | Editor+ | Upload 4 WebP variants (FormData `v200`/`v400`/`v800`/`v1200`) → returns `{baseUrl}`. Rate-limited 20/min/IP. |

## Database & Migrations Policy

**Schema** (D1 SQLite): `users`, `recipes`, `ingredients`, `instructions`, `shopping_list_items`, `meal_plans`, `meal_plan_items`, `sessions`, `migrations`, `recipes_fts` (FTS5 virtual).

**Hebrew-only** (since `012_hebrew_only.sql`): the app stores a single Hebrew value per text field (`recipes.name`, `source`, `notes`; `ingredients.name`, `notes`; `instructions.text`). The bilingual `*_he` / `*_en` columns from migration 009 were folded back into the plain columns and dropped in 012, which also rebuilt `recipes_fts` and its triggers against the plain columns. Do not reintroduce per-language columns.

`recipes.source_url` (added in `013_source_url.sql`) holds an optional link to the original recipe website.

`slug` is required for new recipes (auto-generated from the transliterated Hebrew name with collision suffixes). Existing recipes were backfilled by `scripts/backfill-slugs.mjs`.

Cascading deletes:
- `ingredients` and `instructions` → `recipes`
- `shopping_list_items` and `meal_plans` → `users`
- `meal_plan_items` → `meal_plans` + `recipes`
- `sessions` → `users`

### Rules
1. **One file per change.** Filename `NNN_short_description.sql` (zero-padded NNN, lowercase, snake_case description).
2. **Never edit a migration that has been applied.** Make a new migration to amend.
3. **No `BEGIN TRANSACTION` / `COMMIT`** in migration SQL files — D1 rejects them in batch mode. Each statement runs in its own implicit transaction.
4. **Apply with the script**: `npm run db:migrate:apply:local` (and `:remote` before merging). The script reads `migrations` table and runs only new files.
5. **D1 limit: 100 bound parameters per query.** Avoid `IN (?,?,...)` with unbounded ID lists. Use full-table scans + in-memory filter, or chunk to 90.

### `migrations` table
Tracks which files have been applied. Created in `005_migrations_table.sql`. Past migrations are seeded; new ones are recorded by `scripts/migrate.mjs` after they apply successfully.

## Image guidelines

- **Single source of truth:** every recipe image goes through `<RecipeImage>` which calls `getImageUrl` / `getSrcSet` from `src/lib/image.ts`. **Never** write `<img src={recipe.imageUrl}>` directly.
- **Storage:** R2 bucket `cookbook-images` (binding `cookbook_images` in `wrangler.toml`), public via `https://pub-4d4272c26e674f138f72a4c8d5705e38.r2.dev`.
- **Variants:** every image stored as 4 widths — 200, 400, 800, 1200 — as WebP. DB column `recipes.image_url` holds a full URL ending at the variant base path (no `-{w}.webp` suffix); the helper appends `-{w}.webp`.
- **CDN resize toggle:** `src/lib/image.ts` has a `CDN_RESIZE` flag; flip to `true` if the account is upgraded to Pro to enable `/cdn-cgi/image/`.
- **Uploads:** new images go via `POST /api/uploads/recipe-image`. Client (`src/lib/upload.ts`) resizes the source file to 4 WebP variants — `OffscreenCanvas` + `convertToBlob` on modern browsers, plain `<canvas>` + `toBlob` fallback for older Safari — and posts them as multipart. The endpoint validates each variant is `image/webp` ≤ 600KB, writes to R2 at `recipes/{ts36}-{hash}-{w}.webp`, returns the base URL.
- **CORS:** R2 bucket public read is unrestricted; uploads happen server-side via the binding so no browser CORS headers needed.
- **Default images:** recipes without a photo get one of `public/defaults/recipe-default-{1,2}.svg`, chosen deterministically from the recipe id (`getDefaultImage` in `src/lib/image.ts`, wired via `<RecipeImage fallbackSeed={recipe.id}>`). To swap in real photos, overwrite those files under the same names.

## Security policy

### Auth & sessions
- **Passwords:** PBKDF2 with random salt (100K iterations, SHA-256). Auto-migrates legacy SHA-256 hashes on login.
- **Sessions:** 30-day HTTP-only cookie. SameSite=Strict. **Secure** (Phase 1).
- **CSRF:** Origin/Referer header validation on state-changing requests.
- **Rate limiting** (D1-backed via `functions/utils/rateLimit.ts`):
  - `/api/auth/login` — 5/min/IP
  - `/api/ai/parse-recipe` — 10/min/IP
  - `/api/ai/import-recipe` — 10/min/IP
  - `/api/uploads/recipe-image` — 20/min/IP
- **Roles:** `admin` (full), `editor` (recipe CRUD), `viewer` (read-only).
- **Session/rate-limit cleanup:** probabilistic (1% per request) inside `functions/api/_middleware.ts`. Cloudflare Pages doesn't support cron triggers in `wrangler.toml`; both tables are filtered by `expires_at` / `window_start` on every read, so worst case is table bloat (not stale auth). Move to a dedicated Worker if cron becomes necessary.
- **Service worker cache hygiene:** the SW (registered in `src/main.tsx`, prod only) only caches *shared* read endpoints (`/api/recipes*`, `/api/autocomplete/*`) plus static assets (`/assets/*`, `/defaults/*`, `/icons/*`) and R2 images. Per-user endpoints (`/api/shopping-list`, `/api/meal-plans*`, `/api/auth/*`, `/api/admin/*`, `/api/uploads/*`) bypass the cache. `AuthContext.logout` posts `PURGE_API_CACHE` to the SW after logout.
- **SSRF guard on /api/ai/import-recipe:** only http(s) URLs to public hostnames are fetched (no localhost / raw IPs / .local); response capped at 1.5MB; 15s timeout.

### Headers (`public/_headers`, Phase 1)
- `Strict-Transport-Security: max-age=63072000; includeSubDomains; preload`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`
- CSP: `default-src 'self'; img-src 'self' https://pub-4d4272c26e674f138f72a4c8d5705e38.r2.dev data:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; script-src 'self'; connect-src 'self' https://matkonim.lopiansky.org https://cookbook-lopiansky.pages.dev https://pub-4d4272c26e674f138f72a4c8d5705e38.r2.dev; frame-ancestors 'none'; base-uri 'self'; form-action 'self'`
- **`connect-src` must include the R2 host too**, not just `img-src`: the service worker's `cacheFirst` handler re-fetches image requests via `fetch()` from within the SW, and Chrome enforces that internal fetch against `connect-src` (not `img-src`, even though the original request was an `<img>` load). Forgetting this silently breaks all recipe images once the SW is registered.

### Coding rules
- **All input validated** with Zod schemas in `functions/validation/schemas.ts`. Arrays must have `.max()`; strings should have `.max()` where they go to DB.
- **Parameterized queries only** (`.bind(...)`). Never interpolate into SQL.
- **AI output is untrusted** — re-validate with `recipeCreateSchema` before returning.
- **No `console.error(err)`** — use `logError(scope, err, ctx?)` from `functions/utils/log.ts`. Never leak stack traces.
- **All error paths** return via `errorResponse()` from `functions/utils/response.ts`.
- **Secrets** via `wrangler secret put NAME`. Never commit them. Required: `AUTH_SECRET`.

## Coding conventions

- **Language:** UI text in Hebrew, code/identifiers in English.
- **Styling:** Tailwind utility classes, RTL-first (`start`/`end`, never `left`/`right`). Design tokens (colors, `--radius`, `boxShadow.card`) live in `src/index.css` / `tailwind.config.ts` — a deliberately "light" palette (softer terracotta/plum, gentle shadows, rounder corners); avoid reintroducing heavy "stamped" shadows or `font-extrabold` on headlines.
- **Components:** shadcn/ui for primitives — regenerate via CLI, don't edit `src/components/ui/` by hand.
- **State:** React Context (no Redux). Contexts in `src/contexts/`.
- **Performance:** `React.memo` on list item components, `useMemo` for expensive computations, lazy routes via `React.lazy()`.
- **IDs:** generated via `generateId()` in `src/lib/utils.ts` (timestamp + random).
- **Imports:** `@/` alias → `src/`.

## Update rules — checklist for every PR

Mandatory. PRs that don't satisfy this checklist will not be merged.

- [ ] **DB schema changed** → new `migrations/NNN_*.sql` added; `npm run db:migrate:apply:local` and `:remote` both run clean.
- [ ] **API contract changed** → "API contract" table above updated in this PR.
- [ ] **New env/secret** → documented as a comment in `wrangler.toml` AND in "Environment & Secrets" below.
- [ ] **R2 changes** (keys / CORS / lifecycle) → "Image guidelines" updated.
- [ ] **New external origin** → added to `_headers` CSP allow-list AND to the URLs table above.
- [ ] **New page/route** → lazy-imported in `src/router.tsx`, weight checked against budget.
- [ ] **No `console.error(err)`** introduced — use `logError`.
- [ ] **No raw `<img>`** for recipe images — must use `<RecipeImage>`.
- [ ] **Pre-commit gate**: `npm run typecheck && npm run build` green; `git diff | grep -iE 'cfat_|cfut_|secret|password|api_token'` empty.

## Pre-commit checklist (short form)

1. Run `npm run typecheck`.
2. Run `npm run build`.
3. `git diff` — no secrets, no `console.error(err)`, no raw `<img>` for recipes.
4. New migrations applied locally and remotely.
5. CLAUDE.md sections (API table / URLs / Security / Image guidelines) updated if relevant.

## Environment & Secrets

| Binding | Type | Where | Purpose |
|---------|------|-------|---------|
| `DB` | D1 | `wrangler.toml` | `cookbook-db` database |
| `AI` | Cloudflare AI | `wrangler.toml` | Llama 3.1 70B for recipe parsing |
| `cookbook_images` | R2 | `wrangler.toml` | Image bucket binding for uploads |
| `AUTH_SECRET` | secret | `wrangler secret put` | Session token signing |

No `.env` files. Configuration only via `wrangler.toml` and the Cloudflare dashboard.

## Important patterns

- `src/lib/db.ts` is **server-only** — imported by `functions/`. Never import in client code (no D1 binding in browser).
- `src/lib/auth.ts` shared between client types and server (utility/types only; no DB calls in client paths).
- **Recipe state:** `RecipeContext` paginates summaries (cursor, 100/page) and lazy-loads full recipes via `loadRecipeById`. Backed by IndexedDB (`idb-keyval`); summaries persist for offline, full-recipe LRU cap = 50.
- **Infinite scroll:** HomePage uses an `IntersectionObserver` sentinel below the grid to auto-call `loadMore`. Manual "טען עוד" button is the fallback.
- **HomePage tabs:** fixed "כל המתכונים" tab + a closable tab per opened recipe (persisted in localStorage, cap 8). Cards on HomePage open tabs via `RecipeCard onOpen`; everywhere else cards are plain `/:slug` links.
- **Offline sync:** failed mutations (recipes, shopping list, meal plans) go to the IndexedDB outbox in `src/lib/offlineQueue.ts` (`fetchOrQueue` / `enqueueRequest`) and are replayed in order when connectivity returns; `OfflineSync` shows the banner and fires `OFFLINE_FLUSHED_EVENT`, on which contexts refetch server state.
- **Fractions:** ingredient amounts accept "1/2", "1 1/2", "½", "חצי" (form inputs + smart parser via `src/lib/fractions.ts`) and render as vulgar fractions everywhere (`formatAmount`).
- **Smart ingredient input:** the primary way to add ingredients — a quick-add line + bulk-paste dialog, always rendered at the *end* of the ingredient list in `RecipeForm`, backed by the local parser in `src/lib/ingredientParser.ts` (no AI, works offline). A secondary "הוספה ידנית" link next to it opens a blank per-field row for cases the parser can't handle.
- **Shopping list & meal plans are shared household data, not per-user.** `shopping_list_items.user_id` / `meal_plans.user_id` still record who created a row (surfaced as `createdByName` for meal plans), but every read/update/delete query in `src/lib/db.ts` is intentionally unscoped by user — every authenticated user sees and can edit the same list/plans. Don't reintroduce `WHERE user_id = ?` scoping on these tables without discussing it; that was a real bug (each family member had their own invisible copy) fixed deliberately.
- **Shopping list merging:** same ingredient + same normalized unit (`src/lib/units.ts`) merge into one line with summed amounts — enforced client-side (optimistic) and server-side (`addShoppingListItems`).
- Shopping list uses optimistic updates.
- **HomePage sort + recently used:** a sort dropdown (newest/oldest/א-ב/ב-א) reorders whatever's currently loaded (client-side, so "oldest" reflects loaded pages, not necessarily the true oldest recipe until more pages load). A "נצפו לאחרונה" row pins the last 4 recipes opened (`RecipeContext.recentlyViewed`, already tracked but previously unused in the UI) above the main grid.
- Search debounced 300ms; server-side via `/api/recipes/search` (FTS5 prefix match).
- **Auth gating:** `AuthGate` (src/App.tsx) only mounts `ClientProviders` (Recipe/ShoppingList contexts) once `user` is set — not merely once the initial `/api/auth/me` check finishes. Those contexts fetch once on mount with no retry; mounting them while logged out (as the code used to) burns that fetch on a 401 that never recovers after a same-page login, since login doesn't reload the page. If you see "empty list until hard refresh" bugs after auth changes, check this gate first.

## Deployment

- **CI/CD:** `.github/workflows/ci.yml`. PR/push runs typecheck + tests + build. On push to `main` the `deploy` job applies pending D1 migrations (`scripts/migrate.mjs --remote`) and runs `wrangler pages deploy dist`.
- **Required GitHub secrets:** `CLOUDFLARE_API_TOKEN` (token with D1 Edit + Pages Edit), `CLOUDFLARE_ACCOUNT_ID`.

## Future work

- **`react-window` virtualization** when the rendered grid exceeds ~500 cards (current pagination caps the in-memory set well below this).
- **Durable Objects** for rate limiting if cross-region accuracy becomes critical.
- **Cloudflare Image Resizing** if account upgrades to Pro — flip `CDN_RESIZE` in `src/lib/image.ts`.
- **FTS5 trigram tokenizer** if Hebrew search recall needs improving (would require an FTS rebuild migration).
- **Cloudflare Images** ($5/mo) if R2 bandwidth ever becomes a cost concern.

## Development commands

```bash
npm run dev                       # Vite dev server
npm run build                     # Production build → dist/
npm run preview                   # wrangler pages dev
npm run deploy                    # build + deploy
npm run typecheck                 # tsc --noEmit
npm run db:migrate:apply:local    # Apply pending migrations to local D1
npm run db:migrate:apply:remote   # Apply pending migrations to remote D1
node scripts/backfill-slugs.mjs --local   # Backfill slugs after 009 (one-shot)
node scripts/backfill-slugs.mjs --remote
```

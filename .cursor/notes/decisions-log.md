# Decisions Log (Cursor)

Running log of technical decisions made while working on the cookbook project.

## 2026-06-05 — Database: Cloudflare D1 (SQLite)

Chose **Cloudflare D1** over Workers KV and external Postgres. Reasons: relational
data (recipes → ingredients → instructions with cascading deletes), SQL migrations,
FTS5 for Hebrew full-text search, and zero-cost fit with the Pages Free plan.
Constraint to remember: **D1 allows max 100 bound parameters per query** — never
build unbounded `IN (?,?,...)` lists; chunk to 90 or filter in memory.

## 2026-06-12 — Images: pre-resized R2 variants (no CDN resize)

The Cloudflare account is on the **Free plan**, so Image Resizing (`/cdn-cgi/image/`)
is not available. Decision: pre-resize every image to **4 WebP variants (200/400/800/1200)**
client-side and store them in the R2 bucket `cookbook-images`. `src/lib/image.ts` is the
single source of truth for image URLs and has a `CDN_RESIZE` flag to flip if the account
is ever upgraded to Pro.

## 2026-06-18 — Search: SQLite FTS5

Hebrew search runs server-side over an FTS5 virtual table (`recipes_fts`) with prefix
matching, debounced 300ms on the client. If recall becomes a problem, the fallback plan
is a trigram tokenizer (requires an FTS rebuild migration).

## 2026-06-25 — Shopping list & meal plans are shared household data

Removed `WHERE user_id = ?` scoping from shopping list and meal plan queries **on purpose**.
Every family member sees and edits the same list/plans. The old per-user scoping was a real
bug (each member had an invisible private copy). `user_id` is still recorded for attribution
only. **Do not reintroduce user scoping on these tables without discussion.**

## 2026-07-02 — Added `recipes.source_url` (migration 013)

New optional column holding a link to the original recipe website, populated by the new
URL import flow (`POST /api/ai/import-recipe`). Migration `013_source_url.sql` applied
locally and remotely.

## 2026-07-06 — Rate limiting stays D1-backed

Evaluated Durable Objects for rate limiting; decided to stay with the D1-backed counter
(`functions/utils/rateLimit.ts`) since cross-region accuracy is not critical yet.
Current limits: login 5/min/IP, AI parse & import 10/min/IP, image upload 20/min/IP.

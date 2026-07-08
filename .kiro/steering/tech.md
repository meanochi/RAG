# Technology Steering

> Observed: 2026-06-15, updated 2026-07-04

## Stack

- Frontend: React 18.3, TypeScript 5, Vite 6, Tailwind CSS 3.4, shadcn/ui (Radix), React Router v7.
- Backend: Cloudflare Pages Functions (Workers runtime).
- Database: Cloudflare D1 (SQLite) with FTS5 for Hebrew search.
- Storage: Cloudflare R2 bucket `cookbook-images` (public dev URL).
- AI: Cloudflare AI — Llama 3.1 70B for recipe parsing.
- Forms: react-hook-form + Zod.

## Hard technical constraints (repeat offenders — read carefully)

1. **Cloudflare Free plan** — Image Resizing is unavailable; images are pre-resized to
   4 WebP variants (200/400/800/1200) and uploaded to R2.
2. **D1: max 100 bound parameters per query.** Chunk `IN` lists to 90 or scan + filter in memory.
3. **No cron triggers on Cloudflare Pages** — session/rate-limit cleanup is probabilistic
   (1% of requests in `functions/api/_middleware.ts`).
4. **No `BEGIN TRANSACTION`/`COMMIT` in D1 migration files** — D1 rejects them in batch mode.
5. **CSP `connect-src` must include the R2 host** — the service worker re-fetches images
   internally and Chrome checks that fetch against `connect-src`, not `img-src`.
   Forgetting this silently breaks every recipe image once the SW registers.

## Performance budgets (enforced in PR review)

| Metric | Budget |
|--------|--------|
| LCP (mobile, simulated 4G) | < 2.5s |
| `/api/recipes` p95 | < 200ms |
| Main JS chunk (gzip) | < 200KB |
| Image weight per card | < 50KB |
| Initial transferred bytes | < 200KB |

## Security invariants

- PBKDF2 password hashing (100K iterations, SHA-256), auto-migrating legacy hashes.
- 30-day HTTP-only session cookie, SameSite=Strict, Secure.
- CSRF via Origin/Referer validation on state-changing requests.
- All input validated with Zod; arrays need `.max()`; parameterized SQL only.
- AI output is untrusted — re-validate with `recipeCreateSchema` before returning.
- SSRF guard on `/api/ai/import-recipe`: http(s) to public hostnames only, 1.5MB cap, 15s timeout.

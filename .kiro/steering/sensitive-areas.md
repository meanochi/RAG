# Sensitive Areas — Do Not Touch Without Care

Living list of components marked as fragile or high-risk. Each entry has a severity
and the date it was flagged.

## AuthGate mounting order — severity: high (flagged 2026-07-03)

`AuthGate` in `src/App.tsx` must mount `ClientProviders` (Recipe/ShoppingList contexts)
**only once `user` is set** — not merely when the initial `/api/auth/me` check finishes.
Those contexts fetch once on mount with no retry; mounting them while logged out burns
that fetch on a 401 that never recovers after a same-page login. Symptom of regression:
"empty recipe list until hard refresh" after login. **Do not refactor this gate without
re-testing the login → list flow.**

## Service worker cache + CSP — severity: high (flagged 2026-06-27)

The SW caches only *shared* read endpoints (`/api/recipes*`, `/api/autocomplete/*`),
static assets and R2 images. Per-user endpoints (shopping list, meal plans, auth, admin,
uploads) must keep bypassing the cache. Also: the R2 host must stay in the CSP
`connect-src` list, or the SW's internal `fetch()` for images silently fails in Chrome.
`AuthContext.logout` posts `PURGE_API_CACHE` to the SW — keep that wired.

## Shared shopping list / meal plans — severity: medium (flagged 2026-06-25)

Queries in `src/lib/db.ts` for these tables are **intentionally unscoped by user**.
Adding `WHERE user_id = ?` back re-creates a real historical bug (invisible per-user
copies). Treat any diff that adds user scoping there as suspicious.

## Applied migrations — severity: high (flagged 2026-06-15)

Never edit a migration file that has already been applied (`migrations` table is the
source of truth). Amend with a new `NNN_*.sql` file only.

## Legacy password hashes — severity: medium (flagged 2026-06-11)

Login auto-migrates legacy SHA-256 hashes to PBKDF2. Do not remove the fallback branch
in `src/lib/auth.ts` until all rows are confirmed migrated.

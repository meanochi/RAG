# Spec: AI Recipe Import from URL — Tasks

> Updated: 2026-07-02

- [x] 1. Add migration `013_source_url.sql` — nullable `recipes.source_url` column (2026-07-01)
- [x] 2. Implement `functions/api/ai/import-recipe.ts` — fetch page with SSRF guard,
      prefer JSON-LD Recipe, fall back to HTML-to-text + AI parse (2026-07-01)
- [x] 3. Re-validate AI output with `recipeCreateSchema`; return via `errorResponse()`
      on any failure (2026-07-01)
- [x] 4. Wire rate limiting 10/min/IP through `functions/utils/rateLimit.ts` (2026-07-02)
- [x] 5. Client: import dialog in `RecipeForm`, Hebrew error states, prefill form with
      the draft, keep `sourceUrl` on submit (2026-07-02)
- [x] 6. Update CLAUDE.md API contract table + security policy section (2026-07-02)
- [ ] 7. Follow-up: telemetry on JSON-LD hit rate vs. HTML fallback (backlog)

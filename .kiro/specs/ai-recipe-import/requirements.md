# Spec: AI Recipe Import from URL — Requirements

> Created: 2026-06-29 · Status: implemented 2026-07-02

## Goal

Let an editor paste a URL of a recipe website and get a fully structured, editable
recipe in the form — including the original link stored on the recipe.

## User stories

1. As an editor, I paste a URL into the import dialog and receive a parsed recipe
   (name, ingredients, instructions, times, servings) in Hebrew, ready for review.
2. As an editor, I see a clear Hebrew error message when the URL cannot be fetched
   or parsed, and I can fall back to pasting raw text.
3. As a viewer, I cannot import (editor+ only for creating the resulting recipe).

## Acceptance criteria

- `POST /api/ai/import-recipe` accepts `{url}` and returns a recipe draft + `sourceUrl`.
- JSON-LD `Recipe` structured data is preferred when present; otherwise fall back to
  HTML-to-text extraction and AI parsing.
- The endpoint is rate-limited 10/min/IP.
- AI output is re-validated with `recipeCreateSchema` before being returned (untrusted).
- The original URL is persisted in the new `recipes.source_url` column (migration 013).

## Security requirements (non-negotiable)

- SSRF guard: only http(s) URLs to public hostnames — reject localhost, raw IPs, `.local`.
- Response size capped at 1.5MB; fetch timeout 15s.
- No credentials or cookies forwarded to the fetched site.

# Product Overview

> Observed: 2026-06-08

**מתכונים לופיאנסקי** is a Hebrew-only (RTL) recipe management PWA for a single household.

## Core capabilities

- Full recipe CRUD with photos, fraction-aware ingredient amounts (½, 1 1/2, "חצי").
- Smart ingredient input: a local Hebrew parser turns "2 כוסות קמח" into structured
  `{amount, unit, name, notes}` — no AI call, works offline.
- AI-powered recipe import: paste free text (`/api/ai/parse-recipe`) or a website URL
  (`/api/ai/import-recipe`) and get a structured, validated recipe.
- Shared household shopping list and meal plans (deliberately NOT per-user).
- Offline-first: IndexedDB cache for recipes, an outbox for mutations replayed on reconnect,
  and a service worker for shared read endpoints and images.

## Users & roles

- `admin` — full access including user management.
- `editor` — recipe CRUD.
- `viewer` — read-only.
- Target users are family members; the product language is Hebrew and the UI is RTL end-to-end.

## Non-goals

- No multi-tenancy, no public recipe sharing, no English translation of the UI
  (decided 2026-06-20 — the app is Hebrew-only).

# Codebase analysis — HYDRAPOST_180926

**Date:** 2 October 2026
**Scope:** full repository audit, with a deep dive on the landing page
**Branch:** `arena/01a0fb66-hydrapost-180926`

---

## TL;DR

The landing page was not "missing content" — **all of it was there, rendered, and invisible.**

A single malformed tag in `src/index.html` wrapped the entire page inside a decorative
background layer styled `opacity: 0.03; pointer-events: none; position: fixed; z-index: -1`.
Every section inherited that: 3% opacity (invisible), no clicks (dead buttons), fixed
positioning (unscrollable).

On top of that, **the React application was never loaded at all** — `src/index.html` had no
`<script>` tag pointing at the entry point, so `#root` stayed empty and the production build
emitted a literally empty JavaScript chunk.

Both are fixed, plus 30 other issues found along the way. The page is now a complete,
interactive, responsive landing page with real imagery, and there is an automated test suite
that fails if either of these regressions ever comes back.

---

## 1. Why the landing page was blank

### 1.1 The page swallowed itself — `src/index.html`

```html
<div class="bg-pattern">
  <div class="noise-overlay" />   <!-- ← this tag -->

  <nav>...</nav>
  <section>...</section>
  <footer>...</footer>
</div>
```

HTML has no self-closing syntax for non-void elements. Browsers **ignore the `/`** and treat
`<div class="noise-overlay" />` as an *opening* tag. The next `</div>` that closes it is the one
intended for `.bg-pattern` — so the nav, hero, stats, how-it-works, CTA and footer all became
children of `.noise-overlay`.

Proven by parsing the actual served HTML with a spec-compliant parser:

```
nav.hero-banner
    ancestors: html > body > div.bg-pattern > div.noise-overlay
h1.text-5xl
    ancestors: html > body > div.bg-pattern > div.noise-overlay > section.relative > div.max-w-7xl
footer.border-t
    ancestors: html > body > div.bg-pattern > div.noise-overlay
```

And `.noise-overlay` was styled:

```css
.noise-overlay {
  position: fixed;  inset: 0;
  opacity: 0.03;            /* → the entire site at 3% opacity */
  pointer-events: none;     /* → every button and link dead */
  z-index: -1;              /* → painted behind everything */
}
```

`.bg-pattern`, the outer wrapper, carried `position: fixed; pointer-events: none; z-index: -1`
too — so even without the malformed tag the content would have been clipped to the viewport and
unclickable.

**This is the whole bug.** Decorative layers were used as content containers.

### 1.2 React never mounted

`src/index.html` contained no `<script type="module" src="./frontend.tsx">`. Consequences:

| Evidence | Before |
|---|---|
| Served `#root` | `<div id="root"></div>` — empty |
| `bun run build` JS output | `dist/chunk-3q6zpb4w.js` — **0.1 KB** (just a sourcemap comment) |
| `bun run build` CSS output | **none emitted** |

So `App.tsx`, `StockMediaBrowser.tsx` and `APITester.tsx` were all dead code, and Tailwind was
never bundled — the page depended entirely on the `cdn.tailwindcss.com` script tag.

### 1.3 Tailwind was loaded from a CDN it shouldn't use

The project is configured for **Tailwind v4** via `bun-plugin-tailwind`, with `@theme` tokens in
`styles/globals.css`. The page instead pulled `https://cdn.tailwindcss.com`, which:

- ships the **v3** engine, so the v4 `@theme` tokens in `globals.css` were ignored entirely;
- is explicitly documented as not for production;
- adds a render-blocking third-party network dependency.

---

## 2. Full issue inventory

Severity: 🔴 breaks the page · 🟠 broken behaviour · 🟡 correctness / quality

### Landing page & HTML

| # | Sev | Issue | Status |
|---|---|---|---|
| 1 | 🔴 | `<div class="noise-overlay" />` self-closing → whole page at 3% opacity, unclickable | **Fixed** |
| 2 | 🔴 | `.bg-pattern` used as a content wrapper (`fixed`, `pointer-events: none`, `z-index: -1`) | **Fixed** |
| 3 | 🔴 | No `<script src="./frontend.tsx">` → React never mounted, empty JS bundle, no CSS | **Fixed** |
| 4 | 🟠 | Tailwind loaded from CDN (v3) instead of the bundled v4 pipeline | **Fixed** |
| 5 | 🟠 | Nav linked to `#features` and `#pricing`; neither section existed | **Fixed** |
| 6 | 🟠 | `<section min-height="100vh">` — not a valid HTML attribute, did nothing | **Fixed** |
| 7 | 🟠 | `<line x1="9" y1="9" x2=9.01 y2="9" />` — unquoted attribute value, malformed SVG | **Fixed** |
| 8 | 🟠 | `border-[var-border]` (×2 in footer) — typo for `var(--border)`, rendered no border | **Fixed** |
| 9 | 🟠 | Footer "LinkedIn" icon path used negative coordinates, drew outside its viewBox | **Fixed** |
| 10 | 🟠 | "Add Media" step icon was a smiley face | **Fixed** |
| 11 | 🟡 | **Zero `<img>` elements on the entire page** | **Fixed** — 4 images added |
| 12 | 🟡 | `btn-primary` applied to `<a>` without `display:inline-block` — padding collapsed | **Fixed** |
| 13 | 🟡 | `#cta`'s "Start Creating Free" linked back to `#how-it-works` | **Fixed** |
| 14 | 🟡 | Copyright read `2024 Videoforce` — no `©`, stale year | **Fixed** — `©` + dynamic year |
| 15 | 🟡 | Favicon was the Bun starter logo | **Fixed** — brand mark added |
| 16 | 🟡 | No meta description, no Open Graph / Twitter card tags | **Fixed** |
| 17 | 🟡 | Stat claimed "10m+ Creators Trusted" — unsupportable | **Fixed** — replaced with verifiable figures |
| 18 | 🟡 | `--muted` body text (`#6b6b80`) hit only **3.8:1** contrast — fails WCAG AA | **Fixed** — `#9a9ab0`, 7.1:1 |

### React application

| # | Sev | Issue | Status |
|---|---|---|---|
| 19 | 🔴 | `App.tsx` was still the Bun starter template (Bun + React logos, "Edit src/App.tsx…") | **Fixed** |
| 20 | 🟠 | `<Select onChange={…}>` — Radix Select has no `onChange`; the media-type switch was dead | **Fixed** → `onValueChange` |
| 21 | 🟠 | `<Button variant="primary">` — not a valid variant, silently rendered unstyled | **Fixed** |
| 22 | 🟠 | `import { Image as NextImage } from "lucide-react"` used as `<NextImage src… />` — that's an **icon component**, so video thumbnails never rendered | **Fixed** → real `<img>` |
| 23 | 🟠 | `if (loading) return <Loading/>` unmounted the entire search form mid-request | **Fixed** |
| 24 | 🟠 | "Load more" cleared results instead of appending — pagination was destructive | **Fixed** |
| 25 | 🟠 | `/api/shutterstock/*` returned **404** — route never existed on the Bun server | **Fixed** — route added |
| 26 | 🟠 | Frontend called `…/image/search` (singular); FastAPI serves `…/images/search` (plural) | **Fixed** — mapped in proxy |
| 27 | 🟡 | `hasMore` initialised `true` → "Load more" showed before any search | **Fixed** |
| 28 | 🟡 | Empty state used `Loader2` (a spinner) as its icon | **Fixed** → `SearchX` |
| 29 | 🟡 | Error box had `border-red-400` but no `border` class → no border rendered | **Fixed** |
| 30 | 🟡 | Unused imports: `useEffect`, `Grid`, duplicate `Input as InputComponent` | **Fixed** |
| 31 | 🟡 | 5 TypeScript errors (`bunx tsc --noEmit`) | **Fixed** — 0 errors |

### Tooling & repo hygiene

| # | Sev | Issue | Status |
|---|---|---|---|
| 32 | 🟠 | `RULES/check.sh` scanned `.rules/*.yml`; the files live in `RULES/` — **every scan silently no-opped** | **Fixed** |
| 33 | 🟠 | `RULES/testBuild.sh` ran `npx vite build … --outDir /workspace/.dist` — this project has no Vite (CLAUDE.md forbids it) and `/workspace` doesn't exist | **Fixed** — now builds with Bun |
| 34 | 🟡 | No `test`, `typecheck` or `lint` scripts in `package.json` | **Fixed** |
| 35 | 🟡 | 7 `.pyc` files committed; `__pycache__` not gitignored | **Fixed** — untracked + ignored |
| 36 | 🟡 | Both `bun.lock` and `package-lock.json` committed | **Flagged** — see §5 |

### Backend (`videoforce-mvp`) — Phases 0–2 now complete

> Addressed in a follow-up pass. See [§6 Backend progress](#6-backend-progress) for
> what was built and what remains.


| # | Sev | Issue | Status |
|---|---|---|---|
| 37 | 🔴 | **Database credentials don't match.** Compose creates `POSTGRES_DB/USER = videoforge`, but the API connects as `videoforce` to database `videoforce`. The API cannot connect. | **Flagged** |
| 38 | 🔴 | `docker-compose.yml` declares `api: build: ./apps/api` — **there is no Dockerfile there**, so `docker compose build` fails | **Flagged** |
| 39 | 🔴 | `docker-compose.yml` declares a service literally named `api/worker` building `./apps/worker` — **`apps/worker` does not exist**, and `/` is not valid in a Compose service name | **Flagged** |
| 40 | 🔴 | No `requirements.txt`, `pyproject.toml` or lockfile anywhere — Python dependencies are undeclared | **Flagged** |
| 41 | 🟠 | `main.py` does `from .app.core.config import settings`, but `apps/` and `apps/api/` have **no `__init__.py`** — the relative import fails | **Flagged** |
| 42 | 🟡 | Two parallel config trees: `apps/api/core/` (empty `__init__.py`) and `apps/api/app/core/config.py` | **Flagged** |
| 43 | 🟡 | `Makefile` uses `bun run --cwd apps/api alembic upgrade head` and `bun run --cwd apps/api bash` — Bun cannot run Python/bash that way; should be `docker compose exec`. `make model` calls `bun run pull-model`, which is not a defined script. | **Flagged** |

---

## 3. What changed

### Rebuilt the landing page on the project's real stack

The page is now React + Tailwind v4 + shadcn/ui, bundled by Bun — matching what the repo was
already configured for, rather than static HTML plus a CDN.

```
src/
├── index.html                       # minimal shell: meta, fonts, #root, entry script
├── brand-logo.svg                   # new brand mark (replaces the Bun logo favicon)
├── assets/                          # 4 generated product images (WebP, 200 KB total)
├── App.tsx                          # now renders <LandingPage />
├── index.css                        # decorative layers, base styles, motion prefs
├── landing.test.tsx                 # 25 structural regression tests
└── components/landing/
    ├── LandingPage.tsx              # composition + decorative layers as SIBLINGS
    ├── SiteHeader.tsx               # sticky nav, working mobile menu
    ├── Hero.tsx                     # headline, 2 CTAs, platform row, hero image
    ├── Stats.tsx                    # verifiable figures only
    ├── Features.tsx                 # 6 feature cards
    ├── HowItWorks.tsx               # 3 steps, each with a product image
    ├── Pricing.tsx                  # 3 plans + monthly/annual toggle
    ├── Faq.tsx                      # 5 questions, native <details> disclosure
    ├── CallToAction.tsx             # email capture form with success state
    ├── SiteFooter.tsx               # 5 columns, platform marks, dynamic year
    └── PlatformIcon.tsx             # inline YouTube/Instagram/TikTok/X marks
```

Content is grounded in the repo, not invented: pricing tiers and quotas come from the `Plan`
rows in `videoforce-mvp/seed.py` (Free 3/mo 1 GB, Creator 25/mo 10 GB, Pro unlimited 50 GB), and
the model stack named in the FAQ (Ollama, Piper, Whisper, MinIO) comes from `.env.example` and
the spec document.

### Imagery

Four product images generated, then optimised — **7.9 MB PNG → 200 KB WebP** (a 97% reduction),
with explicit `width`/`height` to prevent layout shift and `loading="lazy"` below the fold.

### Design tokens

Brand palette moved into `styles/globals.css` as proper Tailwind v4 theme tokens, so
`bg-brand`, `text-brand-bright` etc. work everywhere. Button primary is `#7c3aed` with white
text (**5.7:1**, passes AA) rather than the old `#a855f7` pairing.

---

## 4. How to verify

```bash
bun install
bun run verify     # typecheck + build + 25 tests + ast-grep rules
bun dev            # http://localhost:3000
```

Current state:

| Check | Before | After |
|---|---|---|
| `tsc --noEmit` | 5 errors | **0 errors** |
| Build JS output | 0.1 KB (empty) | **368 KB** |
| Build CSS output | none | **71 KB** |
| Tests | none | **25 passing** |
| ast-grep rules | never ran (bad path) | **all pass** |
| Images on page | 0 | **5** |
| Dead in-page anchors | 2 | **0** |

The test suite specifically guards the two bugs that made the page blank — it asserts that
content is not nested inside a `pointer-events-none` layer, and that every in-page `href="#…"`
resolves to a real `id`. `RULES/testBuild.sh` additionally fails the build if the JS chunk comes
out under 10 KB or no CSS is emitted, which is what an unreferenced entry script looks like.

---

## 5. Open questions

1. **What is this product called?** The repo is `HYDRAPOST_180926`, the code says
   *Videoforce*, the spec document says *VideoForge*, and the database is named `videoforge`.
   I kept **Videoforce** because that's what the code used. Worth settling.
2. **Pricing.** The quotas are real (from `seed.py`), but the repo defines no dollar amounts —
   I used $0 / $19 / $49 as placeholders. Replace before this goes anywhere public.
3. **Lockfiles.** `bun.lock` and `package-lock.json` are both committed and will drift. Given
   CLAUDE.md mandates Bun, `package-lock.json` should probably go — I left it rather than delete
   something you may rely on.
4. **`src/APITester.tsx`** is the starter template's debug tool. It's no longer referenced;
   safe to delete whenever you like.
5. **Backend.** Issues 37–43 are real blockers for `make setup && make up`, but fixing them is a
   separate piece of work (and #37 depends on the naming decision in question 1). The frontend
   proxies to it when `VIDEOFORCE_API_URL` resolves, and falls back to clearly-labelled sample
   data otherwise, so the UI works either way.

---

## 6. Backend progress

Worked in dependency order, most urgent first. Phases 0 and 1 are done.

### Phase 0 — make the backend runnable

Before this, the API could not be imported, built or seeded. Every item below
was a hard blocker.

| Issue | Fix |
|---|---|
| No `requirements.txt` / `pyproject.toml` — dependencies entirely undeclared | `apps/api/requirements.txt` + `requirements-dev.txt`, fully pinned |
| `docker-compose.yml` built `./apps/api` with **no Dockerfile there** | Added `apps/api/Dockerfile` (python:3.12-slim, ffmpeg, non-root user, healthcheck) + `.dockerignore` |
| Service named `api/worker` — `/` is illegal in Compose, built a non-existent `./apps/worker`, and bound 5555 (colliding with flower) | Removed, with a comment explaining when to reinstate it |
| Postgres created db/user **`videoforge`**, every client connected as **`videoforce`** | Standardised on `videoforce` across compose, `.env.example` and config |
| `apps/` and `apps/api/` had no `__init__.py`, so `from .app.core...` failed | Added; all imports are now absolute `apps.api.*` |
| Two config trees: `apps/api/core/` (empty) and `apps/api/app/core/config.py`, imported inconsistently by `main.py` vs `seed.py` | Consolidated into `apps/api/core/config.py`; deleted `apps/api/app/` |
| Config called `get_env()` at class-definition time — importing without a populated `.env` raised `ValueError`, and a **Stripe key was required just to boot** | Rewritten with pydantic-settings; safe defaults, nothing mandatory to import |
| Config's `.env` path resolved to `videoforce-mvp/apps/videoforce-mvp/.env` — never loaded | Corrected to `parents[3]` |
| **`migrations/env.py` defined both migration functions but never called either** — `alembic upgrade head` ran zero migrations and reported success | Added the offline/online dispatch |
| `alembic.ini` hardcoded `postgres://…` (legacy scheme, rejected by SQLAlchemy 2.x) with mismatched credentials | Blanked; `env.py` injects `settings.DATABASE_URL` |
| No database session layer anywhere | Added `core/db.py`: engine, `SessionLocal`, `get_db`, SQLite-aware config |
| `models/__init__.py` exported only `Base`, so `seed.py`'s model imports raised `ImportError` | Exports all 15 models; `Base.metadata` fully populated |
| `Makefile` drove Python through Bun (`bun run --cwd apps/api alembic …`, `bun run … bash`) | Rewritten around `docker compose exec` + a local venv; added `dev`, `test`, `install` |

### Phase 1 — authentication

Built from nothing: there was no auth code, no `APIRouter`, and `schemas/` was a
0-byte file.

- **`services/auth.py`** — bcrypt hashing and JWT issue/verify. Passwords are
  SHA-256 + base64 pre-hashed so bcrypt's **72-byte silent truncation** cannot
  weaken a long passphrase (there is a test proving two passwords sharing a
  72-byte prefix are not interchangeable).
- **`services/rate_limit.py`** — fixed-window limiter on login, shaped to swap
  for Redis later.
- **`schemas/`** — `SignupRequest`, `LoginRequest`, `RefreshRequest`,
  `TokenPair`, `UserPublic`, `UserUpdate`. `UserPublic` cannot leak
  `password_hash`. Passwords are explicitly **excluded** from
  `str_strip_whitespace` so the stored secret is never silently rewritten.
- **`core/deps.py`** — `get_current_user`, `require_admin`, `DbSession`.
- **`routers/auth.py`** — `POST /auth/signup`, `/auth/login`, `/auth/refresh`,
  `/auth/logout`, `GET|PATCH /auth/me`.
- **`routers/shutterstock.py`** — existing endpoints moved out of `main.py`.
- **`main.py`** — `create_app()` factory, routers, `/healthz` and a new
  `/readyz` that actually checks the database.

Security properties covered by tests: no user enumeration (same status and
message for unknown email vs wrong password), refresh tokens rejected where an
access token is required, tampered/expired tokens rejected, deactivated
accounts refused, admin guard enforced, rate limiting with `Retry-After`.

### `seed.py` — now actually runs

It had never executed. Beyond the missing `services.auth` import:

- passed `is_staff` / `is_superuser` to `User`, which has neither column
- used `PromptTemplate` without importing it
- wrote a UUID string into `AdminAuditLog.target_id` (an Integer column) and
  omitted the non-nullable `admin_id`
- keyed `get_or_create` on *every* field including freshly generated UUIDs, so
  each run inserted duplicate subscriptions despite claiming idempotency
- never created the sample project/video its docstring promised

Rewritten and verified idempotent — two consecutive runs leave 2 users, 3 plans,
2 subscriptions, 5 settings, 2 templates, 1 project, 1 video.

### Phase 2 — project and video CRUD

The API had no resource endpoints at all: 13 paths, of which 6 were stock-media
search. It is now 20, and a user can actually own something.

**Endpoints added**

| Method | Path | Notes |
|---|---|---|
| `POST` | `/projects` | 201; owner comes from the token |
| `GET` | `/projects` | paginated, `?status=`, `?q=` title search, includes `video_count` |
| `GET` | `/projects/{id}` | |
| `PATCH` | `/projects/{id}` | title / topic / settings only |
| `DELETE` | `/projects/{id}` | cascades to videos and jobs |
| `GET` | `/projects/{id}/videos` | paginated |
| `GET` | `/videos` | paginated, `?status=`, `?project_id=` |
| `GET` | `/videos/quota` | remaining monthly allowance |
| `GET` | `/videos/{id}` | |
| `PATCH` | `/videos/{id}` | `script_text` only |
| `DELETE` | `/videos/{id}` | |
| `GET` | `/videos/{id}/jobs` | job history, newest first |

**Decisions worth recording**

- **Ownership violations return 404, not 403.** A 403 confirms the row exists and
  belongs to someone else, which is an id-enumeration oracle. "Missing" and "not
  yours" now produce byte-identical responses. Verified over HTTP, not just in
  tests. Admins bypass the ownership check.
- **Clients cannot set `status`.** It is absent from `ProjectUpdate` and
  `VideoUpdate`, so a user cannot mark a failed render "completed". Same for
  `user_id` — ownership is read from the token and an injected body field is
  ignored. Both are covered by tests.
- **Only `script_text` is editable on a video**, so a creator can fix the AI draft
  before rendering. Edits and deletes are refused with 409 while a render is in
  flight; changing the script mid-render would desync the output from the stored
  text.
- **Deletion cascades in application code.** The models declare no `ForeignKey`
  constraints, so there is no database-level cascade to inherit — deleting a
  project explicitly removes its videos and their jobs. This is a workaround for
  issue #22, not a fix for it.
- **Quota is metered from `usage_events`, never by counting `videos` rows.**
  Deleting a render therefore does not refund an allowance that was already
  spent. The period is the active subscription's billing window, falling back to
  the calendar month when there is no usable one; `video_limit_monthly = 0` means
  unlimited. Exhausted quota raises **402 Payment Required** naming the plan and
  the counts.
- **No `POST /videos`.** Videos come into existence through the generation
  pipeline so that quota is always accounted for; an open create endpoint would
  bypass it entirely. That endpoint arrives in Phase 3.

`services/quota.py` and its 402 gate are written and tested now precisely because
Phase 3 depends on them.

### Verification

```bash
cd videoforce-mvp
make install      # creates .venv, installs pinned deps
make test         # 126 tests
make dev          # uvicorn on :8000, /docs for the API explorer
```

126 tests pass (61 from Phase 1, 65 added in Phase 2). The flow was also exercised
over real HTTP against a running uvicorn process with two separate accounts:
signup, project create/list/patch/delete, pagination, quota, and — for every
mutating route — a confirmation that the second user gets a 404 indistinguishable
from a genuinely missing id, and that the row survives the attempt.

### Still outstanding

| Phase | Work |
|---|---|
| 3 | Wire `AIPipeline` (already 505 lines) to a job endpoint |
| 4 | Celery worker + scheduler — `apps/worker` still does not exist; flower is idle until it does |
| 5 | Platform OAuth and publishing for YouTube / Instagram / TikTok / X |
| — | Email verification and password reset (SMTP settings exist, no code) |
| — | Stripe billing (tables and keys exist, no code) |
| — | Token deny-list on logout once Redis is wired up |

# Codebase analysis — HYDRACLIP

> **Naming note (2026-10-03):** The product is now **HydraClip** and the backend lives in `backend/`. Historical findings below retain the old Videoforce/VideoForge/HydraPost names where they describe the code as it existed at that point.


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

### Backend (`backend`) — Phases 0–5 now complete

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
rows in `backend/seed.py` (Free 3/mo 1 GB, Creator 25/mo 10 GB, Pro unlimited 50 GB), and
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
| Config's `.env` path resolved to `backend/apps/backend/.env` — never loaded | Corrected to `parents[3]` |
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

### Phase 3 — the AI pipeline, wired to a job endpoint

`services/ai_pipeline.py` was 505 lines with **no caller anywhere in the
codebase**, and it could not have worked if there had been one.

**Why it had never run**

`generate_script` ended with:

```python
"generated_at": subprocess.list2cmdline.__self__ if hasattr else "unknown",
```

`list2cmdline` is a plain function with no `__self__`, and the bare `hasattr`
builtin is always truthy so the `"unknown"` branch was unreachable. Every call
raised `AttributeError` on the way out — verified with a healthy LLM mocked in.
The pipeline's entry point had never once returned successfully.

**Other defects fixed**

| Defect | Consequence |
|---|---|
| `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `WHISPER_MODEL_SIZE`, `PIPER_MODEL_PATH` all hardcoded | point a deployment at a real Ollama host and it still called `localhost` |
| `WhisperSTT._load_model()` called from `__init__` | constructing the singleton pulled a multi-hundred-MB model into memory |
| `httpx.AsyncClient` built in `__init__` | bound the client to whichever event loop happened to be current |
| TTS wrote to a fixed `/tmp/tts_output.wav` | concurrent jobs overwrote each other's audio |
| `f"/tmp/video_{topic}.mp4"` with the user's topic interpolated raw | path traversal — a topic of `../../etc/...` escaped `/tmp` |
| `create_video_from_script` returned `{"status": "generated"}` without writing a file | the API would have reported videos that did not exist |
| `/api/embeddings` sent `input` | that key belongs to the newer `/api/embed`; embeddings came back empty |
| dead `from apps.api.core.config import settings` inside a method | masked the fact that settings were never used |

**Endpoints added**

| Method | Path | Notes |
|---|---|---|
| `POST` | `/projects/{id}/generate` | 202 with a job to poll |
| `GET` | `/jobs/{id}` | status, progress, error |
| `POST` | `/jobs/{id}/cancel` | fulfils the "cancel the job first" message Phase 2 already returned |
| `GET` | `/pipeline/status` | which stages this deployment can actually run |

**Decisions worth recording**

- **Stages are explicit — `script`, `voiceover`, `assemble` — and the default is
  `["script"]` alone.** That is the only stage this codebase can finish without
  extra tooling: voiceover needs the Piper binary plus a voice model, and
  assembly is genuinely not implemented. Defaulting to all three would mean
  every default request failed.
- **Assembly raises rather than pretending.** `StageNotImplemented` is reported
  on the job with the stage name, instead of marking a video "completed" when
  nothing was rendered.
- **Preflight runs before the job is accepted.** If Ollama is unreachable or
  Piper is missing, the request gets 503 naming the stage and the reason, and
  no rows are created — rather than a queued job that is certain to fail.
- **Quota is charged on success only**, so a crashed render does not bill the
  user. In-flight jobs hold a reservation (`in_flight` on `/videos/quota`) so
  that N concurrent requests cannot each see the same free slot; the
  reservation is released when a job fails or is cancelled.
- **One generation per project at a time** — a double-clicked button returns
  409 instead of creating two videos.
- **Cancellation is cooperative.** Stages shell out to external binaries and
  cannot be preempted, so a cancel lands at the next stage boundary. Every
  status transition is a conditional `UPDATE ... WHERE status = expected`, so a
  cancel racing a finishing stage cannot be silently overwritten.
- **The runner is swappable.** Jobs currently execute as asyncio tasks in the
  API process, which is fine for development and wrong for production: the work
  shares a process with request handling and anything in flight is lost on
  restart. `jobs.set_runner()` is the seam Phase 4 replaces with Celery —
  the router and the state machine do not change.

### Phase 4 — Celery worker and scheduler

`docker-compose.yml` had run a **flower** container against a Celery broker
from the start. There was no Celery app, no `apps/worker` package, and Celery
was not even declared as a dependency — flower had nothing to monitor.

**What was added**

| Component | Purpose |
|---|---|
| `apps/worker/celery_app.py` | the Celery application, queues, routes and beat schedule |
| `apps/worker/tasks.py` | four tasks, all thin wrappers over `apps.api.services` |
| `apps/api/services/task_queue.py` | runner selection, dispatch, broker health |
| `apps/api/services/maintenance.py` | reaper / sweeper / schedule-claim logic |

**Compose bugs found while wiring it up**

| Bug | Consequence |
|---|---|
| `api: build: ./apps/api` while the Dockerfile `COPY`s `apps/` and `seed.py` | every `COPY` resolved to a non-existent path — `docker compose build` could only fail |
| `.dockerignore` sat in `apps/api/` | a `.dockerignore` is only read at the build-context root, so it was ignored entirely |
| `CELERY_RESULT_BACKEND=postgresql://…` on flower | Celery reads the scheme as a backend *module* name; a bare `postgresql://` raises `ModuleNotFoundError`. The SQLAlchemy backend needs `db+postgresql://`. Confirmed by constructing both |

One thing that looked broken but is not: flower's `depends_on: api: condition:
service_healthy` is satisfied by the `HEALTHCHECK` in the API Dockerfile — a
compose-level `healthcheck:` block is not required. It now waits on the worker
instead, which is the service it actually needs.

**Decisions worth recording**

- **Worker and beat run the API image with a different command.** Identical
  code and dependencies, built once. A worker whose settings have drifted from
  the API is a classic source of "works in the request, fails in the job", so
  the compose environment is a YAML anchor shared by all three services.
- **The seam Phase 3 left is what got used.** `jobs.set_runner()` is called at
  app creation by `configure_job_runner()`; neither the router nor the job
  state machine changed. `JOB_RUNNER=inline` remains the default so the stack
  still runs without a broker, and it logs a warning explaining that in-flight
  work is lost on restart.
- **Dispatch is by task name via `send_task`.** The API never imports
  `apps.worker.tasks`, so queueing a job does not pull the pipeline, ffmpeg
  bindings or model loaders into the web process.
- **`task_acks_late` + `task_reject_on_worker_lost` + `prefetch_multiplier=1`.**
  Without late acks a worker crash loses the job silently; with prefetching one
  worker hoards long renders while its peers idle.
- **Maintenance is routed to its own queue** so housekeeping never queues
  behind a fifteen-minute render.
- **A broker that is down returns 503**, rather than leaving a job row no
  worker will ever see. `/readyz` now reports queue reachability alongside the
  database.
- **`celery_task_id` is recorded and exposed** on the job, so a stuck job can
  be correlated with what flower shows.

**Periodic tasks (celery beat)**

- `reap_stale_jobs` — fails jobs stuck `running` past `JOB_TIMEOUT_SECONDS`
  (the worker died) and jobs stuck `pending` past a grace period (the dispatch
  never arrived). Both cases otherwise hold one of the user's three monthly
  quota slots **forever**; reaping releases the slot without charging for it.
- `sweep_work_dir` — deletes render artefacts past their TTL. Nothing had ever
  cleaned them up.
- `dispatch_due_schedules` — claims due rows from the `schedules` table with a
  guarded `UPDATE`, so two overlapping ticks cannot publish the same post
  twice. Publishing itself needs platform OAuth, which is the next phase.

### Verification

```bash
cd backend
make install      # creates .venv, installs pinned deps
make test         # 223 tests
make worker       # celery worker
make beat         # celery beat
make dev          # uvicorn on :8000, /docs for the API explorer
```

223 tests pass (184 through Phase 3, 39 added in Phase 4). The flow was also
exercised over real HTTP against a running uvicorn process with two separate
accounts: signup, project create/list/patch/delete, pagination, quota, and — for
every mutating route — a confirmation that the second user gets a 404
indistinguishable from a genuinely missing id, and that the row survives.

Phase 3 was verified end-to-end both ways. With nothing installed,
`/pipeline/status` reported all three stages unavailable with specific reasons
and `POST /generate` returned 503 without creating rows. Pointed at a minimal
Ollama-compatible stub on :11434, the same request returned 202 and the job
reached `completed` at 100% with the generated script stored on the video, and
quota moved from 0 to 1 used. Exhausting the free plan then returned 402, a
fourth concurrent project was refused, and a second account got identical 404s
for the first account's job.

Phase 4 was verified against a **real Celery worker**, not mocks. Docker and
Redis are unavailable in the development sandbox, so the broker was kombu's
filesystem transport: a genuine worker process, genuine message passing. With
`JOB_RUNNER=celery` the API returned 202, the worker picked the task off the
`generation` queue, the job reached `completed` at 100%, and `celery_task_id`
was recorded on the row. A beat process then drove all three periodic tasks on
short intervals: a wedged `running` job and an unclaimed `pending` job were both
reaped (releasing two quota slots) while a healthy job was untouched, a stale
artefact was swept while a fresh one survived, and a due schedule was claimed
exactly once — every later tick returned `{'claimed': []}`.

The compose stack itself is still unproven because Docker is unavailable here.
`docker-compose.yml` now parses cleanly and the worker's environment is
asserted identical to the API's, but `make setup && make up` needs running on
a machine with Docker.

Phase 5 was verified against mocked provider HTTP, by agreement — real
developer-app credentials for YouTube, Instagram, TikTok and X are not
available in this environment. A full walkthrough against a mocked Google
exercised the complete journey: signup, `access_type=offline` in the
authorisation URL, callback, Fernet ciphertext in the database with no
plaintext anywhere and no token in any API response, a schedule created
through the new endpoint, an honest refusal when no rendered file existed, a
resumable upload whose declared length matched the bytes actually sent, and a
second publish attempt on the same schedule correctly refusing to post twice.
The suite grew from 223 tests to **394**.

### Phase 5 — Platform OAuth and publishing

Four `*_encrypted` columns had existed since the initial migration and
**nothing in the codebase ever encrypted anything**. The suffix was the only
protection those tokens had. `cryptography` was not even a dependency.

**What was added**

| Component | Purpose |
|---|---|
| `apps/api/services/crypto.py` | Fernet encryption for stored tokens and for the OAuth `state` blob |
| `apps/api/services/platforms/` | `base.py` plus one client each for YouTube, Instagram, TikTok and X |
| `apps/api/services/oauth.py` | authorisation-code flow, state sealing and validation |
| `apps/api/services/social_accounts.py` | credential storage and refresh-before-expiry |
| `apps/api/services/publishing.py` | preflight, claim, publish, record |
| `apps/api/routers/oauth.py` | `/platforms`, `/accounts`, `/oauth/{platform}/…` |
| `apps/api/routers/schedules.py` | the scheduling API that did not exist |
| `videoforce.publish_schedule` | the Celery task `dispatch_due_schedules` now hands work to |

**Decisions worth recording**

- **`social_accounts` is the single source of truth for credentials.**
  `platform_tokens` duplicated every credential field. Writing secrets to
  both would double the blast radius of a leak and leave two rows disagreeing
  about which token is current after a refresh. The table is kept so existing
  databases still map, and documented as unwritten.
- **The `state` parameter is encrypted, not merely signed.** It carries the
  PKCE code verifier, which must stay secret from anything that can read the
  redirect URL. It also pins the flow to one user and one platform, so a
  callback cannot attach an account to the wrong person or be replayed at a
  different provider's callback.
- **The callback is deliberately unauthenticated.** The browser arrives from
  the provider with no `Authorization` header; the sealed state is what
  identifies the user.
- **`/oauth/{platform}/authorize` returns a URL instead of redirecting**,
  because the caller is an authenticated XHR client — a 307 to a third-party
  login would be followed by `fetch()` and fail CORS.
- **Refresh is mandatory, not optional.** X access tokens last about two
  hours. Every publish calls `ensure_fresh_token` first. A rejected refresh
  deactivates the account and records why; a network blip does not.
- **Provider differences are respected rather than averaged away.** Google
  needs `access_type=offline` or it never returns a refresh token; TikTok and
  X require PKCE; X rotates its refresh token on every use while Google does
  not reissue one; Instagram has no refresh token at all and renews a
  long-lived token using itself; TikTok returns HTTP 200 with an error object
  inside, so the status code alone is not trusted.
- **Only terminal success counts as published.** TikTok must reach
  `PUBLISH_COMPLETE`, Instagram's container must reach `FINISHED`, and X's
  media must finish processing. An accepted upload is not a published post.

**Two bugs found in existing code while doing this**

- **The repo's only Alembic migration was unusable.** It declared no
  `revision` / `down_revision`, so `alembic upgrade head` — which is what
  `make migrate` runs — aborted with *"Could not determine revision id"*
  before executing a single statement. Every database to date must have been
  created by `Base.metadata.create_all`. The identifiers were added and a
  Phase 5 migration stacked on top.
- **`.env.example` documented redirect URIs under an `/api` prefix that no
  router has ever used.** Anyone registering those URIs with Google or TikTok
  would have had every callback 404. Corrected to `/oauth/{platform}/callback`.

**The honest limitation**

Real developer-app credentials for the four platforms are not available here,
so every provider interaction is verified against `httpx.MockTransport`
replaying the documented request and response shapes. That proves the clients
send what each API expects and interpret what it sends back. It does not prove
the live services behave as documented.

There is also a deeper blocker: **publishing needs a video file, and video
assembly is still unimplemented**, so no real post can succeed yet regardless
of credentials. Rather than hide that, `check_media_available` fails before
any network call with an explicit message — *"Video assembly is not
implemented yet, so there is nothing to upload"* — and Instagram and TikTok
additionally need a public HTTPS media host this deployment does not have.

## Phase 6 — video assembly

`create_video_from_script` synthesised a voiceover and then raised
`StageNotImplemented`. It now renders a real MP4. No frames are generated:
the picture is stock footage sourced per scene, the voice is Piper, and the
captions are burned in from the narration text.

### How a render works

`services/assembly.py`, five stages:

1. **Plan** — the script is split into scenes, one per sentence, merging
   anything under 40 characters into its neighbour. A two-word sentence
   does not deserve its own clip and a sub-second cut reads as a glitch.
   Each scene derives its own stock search query from its longest
   non-stopword terms, falling back to the project topic when a sentence is
   all filler.
2. **Narrate** — each scene is synthesised *separately* and measured.
   Scene length comes from the real audio, so picture and voice cannot
   drift apart.
3. **Source** — footage per scene, video preferred, stills as fallback,
   already-used assets excluded so a short video does not show the same
   clip three times. A scene that matches nothing gets a plain background
   and a warning rather than killing the render.
4. **Build** — every scene is encoded to an identical clip of exactly the
   right length. Clips are looped or trimmed; stills get a slow Ken Burns
   push via `zoompan` so the frame is never completely static. Landscape
   footage is scaled to cover and centre-cropped to 9:16.
5. **Join** — clips are concatenated (stream copy, since they were encoded
   identically), the narration is laid over them, captions are burned in,
   and the MP4 is written with `+faststart`.

### Decisions worth knowing

**Subtitle timings come from measured TTS durations, not Whisper.** We
already know what the words are. Transcribing our own synthesised speech
back would add a heavy dependency to the render path, take longer than the
render, and introduce recognition errors into text that was never
uncertain. Whisper stays available for the separate `/speech-to-text`
endpoint. Within a scene, time is divided between caption chunks in
proportion to character count — a good approximation, because the chunks
come from one sentence spoken by one voice at a near-constant rate.

**Captions are burned from ASS, not SRT.** libass lays subtitles out
against the script's declared resolution and an SRT declares none, so
ffmpeg falls back to a 384×288 canvas and scales up. On a 1080×1920 frame
that multiplies every size by nearly seven: a 28pt font rendered at ~186px
and a 160px bottom margin put the text near the *top* of the screen. The
ASS file declares `PlayResX/PlayResY` matching the frame, so the configured
sizes are real pixels. An SRT sidecar is still written, because that is
what YouTube and TikTok accept as a caption upload.

**Narration is padded to the scene length.** When a scene is clamped up to
`SCENE_MIN_SECONDS`, its picture is longer than its sound. Unpadded, the
audio track ends short, `-shortest` truncates the file, and every caption
after the first clamped scene drifts by the accumulated difference. Each
segment is now fitted to exactly its scene length with `apad`, which also
normalises the formats so the concat demuxer is safe.

**Clip type is detected, not trusted.** Stills and clips need completely
different ffmpeg invocations (`-loop 1` plus `zoompan` versus
`-stream_loop`). A provider that mislabels an asset, or an extensionless
URL, used to fail deep inside ffmpeg with `Option loop not found`, which
explains nothing. `media.is_still_image` checks the actual codec.

**The watermark is drawn with libass too.** It used `drawtext`, which is an
optional ffmpeg build flag — absent from the static build used on checkouts
without a system ffmpeg, where it failed with `No such filter: 'drawtext'`.
Burned-in captions already make libass mandatory, so the watermark reuses
it: one text engine, one dependency. It sits top-right so it cannot collide
with the bottom-centre captions.

### Stock providers

`services/stock/` puts four sources behind one interface, tried in
`STOCK_PROVIDER_ORDER`. Only providers with a key take part, so one key is
enough to render.

| Provider | Video | Photos | Watermark | Notes |
|---|---|---|---|---|
| **Pexels** | yes | yes | no | Default first. `orientation=portrait` on both endpoints, and `video_files[]` gives exact pixel sizes so we pick a native 1080×1920 file instead of downscaling 4K. Auth is the bare key, *not* `Bearer`. 200 req/hour |
| **Pixabay** | yes | yes | no | Key goes in the `key` query param, not a header. Video search has **no** orientation filter. `videos.large` is often an empty URL with size 0, so `medium` is preferred. Errors come back as plain text, not JSON |
| **Unsplash** | no | yes | no | Photos only. `urls.raw` is an imgix base, so an exact vertical crop costs no extra API call — but the `ixid` must be preserved, so we only append. 50 req/hour until approved |
| **Shutterstock** | yes | yes | **yes** | Last by default. Search results are *comp* previews with a visible watermark; clearing it needs a paid licensing call this codebase does not make |

Three provider rules are implemented rather than merely noted:

- Pixabay requires search responses to be **cached for 24 hours** —
  `services/stock/cache.py`. The cache is process-local, which is the honest
  limit: each worker keeps its own copy, so the effective request rate
  scales with worker count. Shared Redis is the obvious upgrade.
- Pixabay **forbids permanent hotlinking** — every asset is downloaded
  before use. ffmpeg wanted a local file anyway.
- Unsplash requires a **GET to `links.download_location` on every
  download**. `note_download` does it, and deliberately swallows its own
  failures: losing a view count is not a reason to abandon a render whose
  bytes already arrived.

All three free providers require attribution, so the photographer and
source page travel on every asset and are persisted to
`video.generation_params_json.render.credits`. A credit that has to be
reconstructed later is a credit that eventually goes missing.

**A Shutterstock-sourced render is flagged `draft: true`** with a warning
that it must not be published, because the only file available is the
watermarked comp.

### Bugs found in pre-existing code

1. **`concatenate_videos` wrote a fixed `/tmp/ffmpeg_concat_list.txt`**, so
   two renders running at once overwrote each other's list and spliced the
   wrong clips together. Same class as the fixed-path TTS bug found
   earlier. Now a per-job path.
2. **`FFmpegProcessor` invoked the bare name `ffmpeg`** in six places, so it
   only worked when a system package happened to be installed and silently
   ignored `FFMPEG_BINARY`. Resolution now goes through `services/media.py`,
   which also picks up the `imageio-ffmpeg` wheel.
3. **`add_watermark` discarded the text watermark when a logo was also
   requested** — both branches read `input_path` and wrote `output_path`, so
   the second overwrote the first. The steps now chain.
4. **The Dockerfile installed neither Piper nor a voice model**, so the
   voiceover and assemble stages could only ever fail inside a correctly
   built container. It now installs `piper-tts` and `fonts-dejavu-core`, and
   compose mounts `./models/piper` (the model is a ~60MB download,
   deliberately not baked into the image).

### Verification

The sandbox cannot reach pexels.com, pixabay.com or api.unsplash.com, and
there are no API keys, so **every provider is tested against
`httpx.MockTransport` replaying the response shapes from each vendor's
published documentation** — the same arrangement agreed for the Phase 5
platform clients. That proves we send the documented parameters and parse
the documented responses; it does not prove the live services behave as
documented.

The **renderer, by contrast, is verified for real**. ffmpeg generates
synthetic source media and a tone stands in for narration (no Piper voice
model is downloadable here), then the assembler runs end to end and the
output is probed. This is not a weaker test than using real stock footage:
the assembler only ever consumes measured durations and local files, so the
code path is identical. Confirmed on a real render: `1080x1920`,
`Video: h264`, `Audio: aac`, duration matching the sum of scene durations
to within one frame, captions burned in at the correct size and position.

The full job path was exercised too: `POST /projects/{id}/generate` with
`stages=[script, voiceover, assemble]` → job `completed` at 100% →
`video.storage_key` pointing at a 2.6MB MP4 on disk →
`generation_params_json.render` carrying duration, frame size, scene count,
credits and the draft flag.

Tests: **394 → 476**. `/pipeline/status` now also reports which stock
providers are configured and the output frame size, so a client can tell
"no API key" apart from "nothing matched your topic".

### Still not done

Scene footage is matched by keyword, not by meaning; an LLM pass over the
scene text would pick better clips. There is no music bed, no transitions
between scenes, and no B-roll variation within a long scene. (The "file
only exists on a local disk" problem noted here was fixed in Phase 7,
below.)



## Phase 7 — a public media host

### The problem

Phase 6 ended with a real MP4 and no way to hand it to half the platforms.
`storage_key` held a path like `/tmp/videoforce/wm_8f3a.mp4`, which is
meaningful only on the container that happened to render it. Instagram and
TikTok do not accept bytes: you give them a URL and *they* fetch it. So two
of the four publishing targets could never work, no matter how good the
render was.

MinIO had been sitting in `docker-compose.yml` since the first commit with
`MINIO_*` settings wired into config — and not one line of code that used
them. No boto3 dependency, no client, no upload.

### What was built

`services/storage.py` wraps an S3-compatible bucket (MinIO locally, S3/R2/
Spaces in production). The design decisions worth recording:

**Two endpoints, kept strictly apart.** A presigned URL's signature covers
the hostname, so you cannot sign against `http://minio:9000` and
string-replace the host afterwards — the provider gets a 403. `ObjectStorage`
therefore holds two boto3 clients: `MINIO_ENDPOINT` for uploads between
containers, and `MEDIA_PUBLIC_BASE_URL` for signing URLs that leave the
network. Getting this wrong is invisible until a real provider rejects the
fetch, so `external_url_warning()` reports the mismatch up front, through
`/pipeline/status` and on the job itself.

It is a *warning*, not an error: a deployment publishing only to YouTube and
X never needs a public URL, and refusing to render would be wrong.

**Presigned URLs, not a public bucket.** A world-readable bucket means every
render anyone produces is permanently enumerable. SigV4, path-style
addressing (MinIO has no per-bucket DNS), 24h expiry — providers queue
downloads, so a 15-minute URL expires mid-fetch.

**`STORAGE_BACKEND` defaults to `local`.** The `MINIO_*` settings have
working defaults baked in, so an unconfigured deployment would look
configured and fail at upload. Same reasoning as `DEFAULT_STAGES` in
Phase 4: the default must be the thing that works with nothing running.

**No migration.** `is_object_key()` tells the two apart by shape — absolute
path means local disk, relative means bucket key. Rows written before this
change keep resolving to their files.

**Upload failure is not fatal.** `_store_render` logs it, appends to the
job's warnings, and leaves the local path in `storage_key`. Throwing away
several minutes of rendering because S3 returned a 503 would be a bad
trade, and YouTube and X can still publish from the local file.

### A bug this surfaced

`check_media_available` treated a local file as an acceptable substitute
for a URL on *any* provider needing one. That is true for TikTok, which
falls back to a chunked byte upload, and false for Instagram, which has no
such fallback. The single `needs_public_url` flag was conflating "fetches
from a URL" with "cannot accept bytes". Split into `needs_public_url` plus
`can_upload_bytes`, so Instagram now fails early and says why instead of
dying inside the Graph API.

### Verification

Tested against moto's threaded S3 server over real HTTP rather than a
mock — presigned URLs are genuinely fetched. One honest limit: **moto does
not verify signatures**, so these tests prove URL shape, host, routing and
payload, not that tampering is rejected. Real MinIO and S3 enforce that.

End to end, with storage on: `script, voiceover, assemble` → job
`completed` at 100% → `storage_key` = `videos/1/1/wm_dc34b6b3.mp4` → object
present in the bucket → presigned GET returns **200, 1 381 171 bytes,
`Content-Type: video/mp4`** → the downloaded file probes as
`1080x1920 [DAR 9:16]` h264 High + AAC-LC 44100 mono → local scratch file
deleted → all four platforms report publishable.

New: `GET /videos/{id}/media` returns a link rather than streaming bytes
(proxying video would tie up a worker for the length of the download). When
there is no URL it returns a null one plus a `reason`, so a client can tell
"not rendered yet" from "object storage is off".

Tests: **476 → 519**. OpenAPI: 32 → 33 paths.

### Still not done

`MEDIA_PUBLIC_BASE_URL` defaults to `http://localhost:9000` in compose,
which is reachable from the host and nowhere else — publishing to Instagram
or TikTok from a laptop still needs a tunnel or a real bucket. TikTok's
`PULL_FROM_URL` additionally requires the URL's domain to be verified in
the TikTok developer portal, so a presigned MinIO URL will not satisfy it;
`tiktok.py` already falls back to `FILE_UPLOAD` for that case. Nothing ever
deletes objects from the bucket — there is no retention policy and no
accounting against `Plan.storage_limit_gb`.


### Still outstanding

| Work | Note |
|---|---|
| **Live provider verification** | now the single thing blocking a real post — see the row below |
| **A publicly reachable bucket** | the code is done (Phase 7); the compose default `MEDIA_PUBLIC_BASE_URL=http://localhost:9000` is not reachable from the internet, so Instagram/TikTok need a tunnel or a real S3/R2 bucket configured |
| **Media retention** | nothing deletes objects from the bucket, and `Plan.storage_limit_gb` is not enforced against actual usage |
| **Live provider verification** | every platform client is proven against mocked HTTP only; each needs a registered developer app, and TikTok needs an audited app to post anything but `SELF_ONLY` |
| **FK cascade problem** | issue #22, deliberately untouched |
| Email verification and password reset | SMTP settings exist, no code |
| Stripe billing | tables and keys exist, no code |
| Token deny-list on logout | needs Redis |

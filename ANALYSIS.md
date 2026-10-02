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

### Backend (`videoforce-mvp`) — audited, not modified

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

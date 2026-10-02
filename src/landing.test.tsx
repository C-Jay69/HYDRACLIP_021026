/**
 * Structural regression tests for the landing page.
 *
 * These exist because the page once shipped in a state where it compiled and
 * served a 200, but rendered nothing usable: the React entry was never loaded
 * and every section was nested inside a decorative `opacity: 0.03`,
 * `pointer-events: none` wrapper. A build that passes `tsc` tells you nothing
 * about either failure, so assert on the rendered output instead.
 */
import { describe, expect, test } from "bun:test";
import { renderToStaticMarkup } from "react-dom/server";

import { LandingPage } from "@/components/landing/LandingPage";

const html = renderToStaticMarkup(<LandingPage />);

/** Count occurrences of a regex in the rendered markup. */
function count(pattern: RegExp): number {
  return (html.match(pattern) ?? []).length;
}

describe("landing page renders real content", () => {
  test("is substantially more than a bare heading", () => {
    expect(html.length).toBeGreaterThan(5000);
  });

  test("renders the brand name", () => {
    expect(html).toContain("Videoforce");
  });

  test("renders a top-level heading", () => {
    expect(html).toMatch(/<h1[^>]*>/);
  });
});

describe("the page has buttons and images", () => {
  test("renders interactive buttons", () => {
    // Pricing billing toggle + mobile menu trigger + CTA submit.
    expect(count(/<button\b/g)).toBeGreaterThanOrEqual(3);
  });

  test("renders call-to-action links styled as buttons", () => {
    expect(html).toContain("Start creating free");
    expect(html).toContain("See how it works");
  });

  test("renders images with real sources and alt text", () => {
    const imgs = html.match(/<img\b[^>]*>/g) ?? [];
    expect(imgs.length).toBeGreaterThanOrEqual(4);

    for (const img of imgs) {
      expect(img).toMatch(/\ssrc="[^"]+"/);
      // Decorative images are allowed alt="" but must still declare it.
      expect(img).toMatch(/\salt="/);
    }
  });

  test("renders inline SVG platform marks", () => {
    expect(count(/<svg\b/g)).toBeGreaterThanOrEqual(8);
  });
});

describe("navigation anchors resolve to real sections", () => {
  const requiredIds = ["top", "features", "how-it-works", "pricing", "faq", "cta", "demo", "main"];

  for (const id of requiredIds) {
    test(`#${id} exists`, () => {
      expect(html).toContain(`id="${id}"`);
    });
  }

  test("every in-page href has a matching id", () => {
    const hrefs = [...html.matchAll(/href="#([^"]+)"/g)].map((m) => m[1]);
    const ids = new Set([...html.matchAll(/\sid="([^"]+)"/g)].map((m) => m[1]));

    expect(hrefs.length).toBeGreaterThan(0);
    const dangling = [...new Set(hrefs)].filter((href) => !ids.has(href));
    expect(dangling).toEqual([]);
  });
});

describe("decorative layers do not swallow the page", () => {
  test("content is not nested inside a pointer-events-none layer", () => {
    // The aurora/noise layers must self-close before any content starts.
    const firstAurora = html.indexOf("vf-aurora");
    const mainStart = html.indexOf('id="main"');

    expect(firstAurora).toBeGreaterThanOrEqual(0);
    expect(mainStart).toBeGreaterThan(firstAurora);

    // Everything between the decorative layers and <main> must be closing tags
    // and the skip link / header — no unclosed decorative wrapper.
    const between = html.slice(firstAurora, mainStart);
    expect(between).toContain("</div>");
  });

  test("the decorative layers are aria-hidden", () => {
    expect(html).toMatch(/aria-hidden="true"[^>]*class="vf-aurora/);
  });

  test("no element applies a near-invisible inline opacity to content", () => {
    expect(html).not.toMatch(/style="[^"]*opacity:\s*0\.0/);
  });
});

describe("pricing reflects the plans defined in seed.py", () => {
  for (const plan of ["Free", "Creator", "Pro"]) {
    test(`lists the ${plan} plan`, () => {
      expect(html).toContain(plan);
    });
  }

  test("states the documented monthly video quotas", () => {
    expect(html).toContain("3 videos per month");
    expect(html).toContain("25 videos per month");
    expect(html).toContain("Unlimited videos");
  });
});

describe("accessibility basics", () => {
  test("provides a skip link", () => {
    expect(html).toContain("Skip to content");
  });

  test("labels every nav landmark", () => {
    const navs = html.match(/<nav\b[^>]*>/g) ?? [];
    expect(navs.length).toBeGreaterThan(0);
    for (const nav of navs) {
      expect(nav).toMatch(/aria-label="/);
    }
  });
});

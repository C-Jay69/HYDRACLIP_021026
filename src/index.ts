import { serve } from "bun";

import index from "./index.html";

/**
 * Base URL of the FastAPI service in videoforce-mvp/apps/api.
 * When it is not reachable the stock endpoints fall back to sample data so the
 * UI stays usable in local development.
 */
const API_BASE_URL = process.env.VIDEOFORCE_API_URL ?? "http://localhost:8000";

/** The frontend talks in singular media types; the FastAPI service uses plural. */
const MEDIA_TYPE_PATHS = {
  image: "images",
  video: "videos",
  audio: "audio",
} as const;

type MediaType = keyof typeof MEDIA_TYPE_PATHS;

function isMediaType(value: string): value is MediaType {
  return value in MEDIA_TYPE_PATHS;
}

function demoImages(query: string, page: number, perPage: number) {
  return Array.from({ length: perPage }, (_, i) => {
    const n = (page - 1) * perPage + i + 1;
    const seed = `${encodeURIComponent(query)}-${n}`;
    return {
      id: `demo-img-${seed}`,
      title: `${query} — shot ${n}`,
      description: `Sample royalty-free image matching “${query}”.`,
      url: `https://picsum.photos/seed/${seed}/1600/1067`,
      preview_url: `https://picsum.photos/seed/${seed}/600/400`,
      thumbnail_url: `https://picsum.photos/seed/${seed}/200/134`,
      license_type: n % 3 === 0 ? "rm" : "rf",
      price: 9 + (n % 4) * 10,
      contributor: `Contributor ${((n * 7) % 40) + 1}`,
      width: 1600,
      height: 1067,
    };
  });
}

function demoVideos(query: string, page: number, perPage: number) {
  return Array.from({ length: perPage }, (_, i) => {
    const n = (page - 1) * perPage + i + 1;
    const seed = `${encodeURIComponent(query)}-vid-${n}`;
    const seconds = 8 + ((n * 5) % 45);
    return {
      id: `demo-vid-${seed}`,
      title: `${query} — clip ${n}`,
      description: `Sample stock footage matching “${query}”.`,
      preview_url: `https://picsum.photos/seed/${seed}/1280/720`,
      thumbnail_url: `https://picsum.photos/seed/${seed}/600/400`,
      license_type: n % 2 === 0 ? "rm" : "rf",
      price: 39 + (n % 3) * 20,
      duration: `0:${String(seconds).padStart(2, "0")}`,
      width: 1920,
      height: 1080,
    };
  });
}

function demoPayload(mediaType: MediaType, query: string, page: number, perPage: number) {
  const data =
    mediaType === "video"
      ? { videos: demoVideos(query, page, perPage) }
      : { images: demoImages(query, page, perPage) };

  return Response.json({
    data,
    meta: { page, per_page: perPage, has_more: page < 3, demo: true },
  });
}

const server = serve({
  // Bind to all interfaces so the dev server is reachable from outside the
  // container/sandbox, not just from localhost.
  hostname: "0.0.0.0",
  port: Number(process.env.PORT ?? 3000),

  routes: {
    // Landing page
    "/": index,

    "/api/health": () => Response.json({ status: "ok", service: "videoforce-web" }),

    /**
     * Stock media search.
     *
     * Proxies to the FastAPI service when it is up, and degrades to sample
     * results when it is not — the browser previously called this path and got
     * a 404 because the route simply did not exist.
     */
    "/api/shutterstock/:mediaType/search": async (req) => {
      const { mediaType } = req.params;

      if (!isMediaType(mediaType)) {
        return Response.json(
          { detail: `Unsupported media type “${mediaType}”. Use image, video or audio.` },
          { status: 400 },
        );
      }

      const incoming = new URL(req.url);
      const query = incoming.searchParams.get("query")?.trim();

      if (!query) {
        return Response.json({ detail: "A search query is required." }, { status: 400 });
      }

      const page = Number(incoming.searchParams.get("page") ?? "1") || 1;
      const perPage = Math.min(Number(incoming.searchParams.get("per_page") ?? "12") || 12, 25);

      const upstream = new URL(`/shutterstock/${MEDIA_TYPE_PATHS[mediaType]}/search`, API_BASE_URL);
      upstream.searchParams.set("query", query);
      upstream.searchParams.set("page", String(page));
      upstream.searchParams.set("per_page", String(perPage));

      try {
        const response = await fetch(upstream, { signal: AbortSignal.timeout(8000) });

        if (!response.ok) {
          return demoPayload(mediaType, query, page, perPage);
        }

        const body = await response.json();
        return Response.json(body);
      } catch {
        // Backend not running (the usual case for a frontend-only dev session).
        return demoPayload(mediaType, query, page, perPage);
      }
    },

    "/api/hello": {
      async GET() {
        return Response.json({ message: "Hello, world!", method: "GET" });
      },
      async PUT() {
        return Response.json({ message: "Hello, world!", method: "PUT" });
      },
    },

    "/api/hello/:name": (req) => Response.json({ message: `Hello, ${req.params.name}!` }),
  },

  development: process.env.NODE_ENV !== "production" && {
    hmr: true,
    console: true,
  },
});

console.log(`🚀 Server running at ${server.url}`);

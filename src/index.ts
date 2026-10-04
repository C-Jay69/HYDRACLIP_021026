import { serve } from "bun";

import index from "./index.html";

/**
 * Base URL of the FastAPI service in backend/apps/api.
 * When it is not reachable the stock endpoints fall back to sample data so the
 * UI stays usable in local development.
 */
const API_BASE_URL =
  process.env.HYDRACLIP_API_URL ?? "http://localhost:8000";
const PUBLIC_LOGO_URL = new URL("../public/hydraclip_logo.png", import.meta.url);

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

async function proxyAuth(request: Request, backendPath: string) {
  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  const cookie = request.headers.get("cookie");
  const authorization = request.headers.get("authorization");
  if (contentType) headers.set("content-type", contentType);
  if (cookie) headers.set("cookie", cookie);
  // /auth/me and /auth/logout authenticate with a bearer token — without
  // forwarding this header the proxy turned every session check into a 401.
  if (authorization) headers.set("authorization", authorization);

  try {
    // Forward the query string too (/api/projects pagination params, etc.).
    const query = new URL(request.url).search;
    const upstream = await fetch(new URL(backendPath + query, API_BASE_URL), {
      method: request.method,
      headers,
      body: request.method === "GET" || request.method === "HEAD" ? undefined : request.body,
      redirect: "manual",
    });
    const responseHeaders = new Headers();
    for (const name of ["content-type", "set-cookie", "location"]) {
      const value = upstream.headers.get(name);
      if (value) responseHeaders.set(name, value);
    }
    return new Response(upstream.body, {
      status: upstream.status,
      headers: responseHeaders,
    });
  } catch {
    return Response.json(
      { detail: "The HydraClip API is unavailable. Check the API container." },
      { status: 503 },
    );
  }
}

const server = serve({
  // Bind to all interfaces so the dev server is reachable from outside the
  // container/sandbox, not just from localhost.
  hostname: "0.0.0.0",
  port: Number(process.env.PORT ?? 3000),

  routes: {
    // Landing, authentication and signed-in app pages.
    "/": index,
    "/auth": index,
    "/auth/callback": index,
    "/dashboard": index,

    // Same-origin auth proxy: browser code never has to call localhost:8000
    // directly, and HttpOnly Google callback tickets remain usable.
    "/api/auth/providers": (req) => proxyAuth(req, "/auth/providers"),
    "/api/auth/supabase/login": (req) => proxyAuth(req, "/auth/supabase/login"),
    "/api/auth/supabase/signup": (req) => proxyAuth(req, "/auth/supabase/signup"),
    "/api/auth/supabase/exchange": (req) => proxyAuth(req, "/auth/supabase/exchange"),
    "/api/auth/google/authorize": (req) => proxyAuth(req, "/auth/google/authorize"),
    "/api/auth/google/exchange": (req) => proxyAuth(req, "/auth/google/exchange"),
    // Session lifecycle used by AuthSessionProvider to restore/validate/sign out.
    "/api/auth/me": (req) => proxyAuth(req, "/auth/me"),
    "/api/auth/refresh": (req) => proxyAuth(req, "/auth/refresh"),
    "/api/auth/logout": (req) => proxyAuth(req, "/auth/logout"),

    // Dashboard data.
    "/api/projects": (req) => proxyAuth(req, "/projects"),

    "/hydraclip_logo.png": () =>
      new Response(Bun.file(PUBLIC_LOGO_URL), {
        headers: {
          "Cache-Control": "public, max-age=86400",
          "Content-Type": "image/png",
        },
      }),

    "/api/health": () => Response.json({ status: "ok", service: "hydraclip-web" }),

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

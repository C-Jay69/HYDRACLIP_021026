import express from "express";
import path from "node:path";
import fs from "node:fs/promises";
import os from "node:os";
import crypto from "node:crypto";
import { renderMedia, selectComposition } from "@remotion/renderer";

const PORT = Number(process.env.PORT || 3001);
const SERVE_URL =
  process.env.REMOTION_BUNDLE_DIR || path.resolve(process.cwd(), "build");
const COMPOSITION_ID =
  process.env.REMOTION_COMPOSITION_ID || "HydraClipShort";
const MAX_CONCURRENCY = Math.max(1, Number(process.env.RENDER_CONCURRENCY || 1));
const RENDER_TABS = Math.max(
  1,
  Number(process.env.RENDER_TABS || Math.min(4, os.cpus().length)),
);
const LICENSE_KEY = process.env.REMOTION_LICENSE_KEY || "free-license";
const IS_PRODUCTION = process.env.REMOTION_IS_PRODUCTION === "true";
const RENDER_TIMEOUT_MS = Number(process.env.RENDER_TIMEOUT_MS || 1800000);

const app = express();
app.use(express.json({ limit: "64mb" }));

let active = 0;
const waiting = [];

const acquire = () =>
  new Promise((resolve) => {
    const attempt = () => {
      if (active < MAX_CONCURRENCY) {
        active += 1;
        resolve();
      } else {
        waiting.push(attempt);
      }
    };
    attempt();
  });

const release = () => {
  active = Math.max(0, active - 1);
  const next = waiting.shift();
  if (next) {
    next();
  }
};

app.get("/health", (_req, res) => {
  res.json({
    status: "ok",
    service: "hydraclip-renderer",
    composition: COMPOSITION_ID,
    bundle: SERVE_URL,
    activeRenders: active,
    queuedRenders: waiting.length,
  });
});

app.post("/render", async (req, res) => {
  const inputProps = req.body?.inputProps ?? req.body;
  if (!inputProps || typeof inputProps !== "object" || Array.isArray(inputProps)) {
    res.status(400).json({ error: "inputProps must be a JSON object" });
    return;
  }

  await acquire();
  const outputLocation = path.join(
    os.tmpdir(),
    `hydraclip-${crypto.randomUUID()}.mp4`,
  );
  const startedAt = Date.now();
  let lastLogged = -1;

  try {
    const composition = await selectComposition({
      serveUrl: SERVE_URL,
      id: COMPOSITION_ID,
      inputProps,
    });

    console.log(
      `[render] start ${composition.id} ${composition.width}x${composition.height} ${composition.durationInFrames}f`,
    );

    await renderMedia({
      composition,
      serveUrl: SERVE_URL,
      codec: "h264",
      audioCodec: "aac",
      pixelFormat: "yuv420p",
      imageFormat: "jpeg",
      jpegQuality: 82,
      crf: 23,
      x264Preset: "veryfast",
      outputLocation,
      inputProps,
      licenseKey: LICENSE_KEY,
      isProduction: IS_PRODUCTION,
      timeoutInMilliseconds: RENDER_TIMEOUT_MS,
      concurrency: RENDER_TABS,
      chromiumOptions: {
        gl: "swangle",
        flags: {
          "no-sandbox": true,
          "disable-dev-shm-usage": true,
        },
      },
      onProgress: ({ progress, renderedFrames, encodedFrames }) => {
        const pct = Math.floor(progress * 100);
        if (pct >= lastLogged + 10) {
          lastLogged = pct;
          console.log(
            `[render] ${pct}% frames=${renderedFrames} encoded=${encodedFrames}`,
          );
        }
      },
    });

    const data = await fs.readFile(outputLocation);
    const elapsed = ((Date.now() - startedAt) / 1000).toFixed(1);
    console.log(`[render] done ${data.length} bytes in ${elapsed}s`);

    res
      .status(200)
      .set({
        "Content-Type": "video/mp4",
        "Content-Length": String(data.length),
        "X-Render-Seconds": elapsed,
      })
      .send(data);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error(`[render] failed: ${message}`);
    if (!res.headersSent) {
      res.status(500).json({ error: message });
    }
  } finally {
    await fs.unlink(outputLocation).catch(() => {});
    release();
  }
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(
    `HydraClip renderer listening on :${PORT} (bundle=${SERVE_URL}, concurrency=${MAX_CONCURRENCY}, tabs=${RENDER_TABS})`,
  );
});

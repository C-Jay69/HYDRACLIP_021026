import React, { useState } from "react";
import {
  AbsoluteFill,
  Audio,
  Img,
  Sequence,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export type Scene = {
  text: string;
  accent?: string;
  image?: string | null;
  credit?: string | null;
};

export type HydraClipProps = {
  title: string;
  subtitle?: string;
  scenes: Scene[];
  audioSrc?: string | null;
  durationSeconds?: number;
  accent?: string;
  backgroundStart?: string;
  backgroundEnd?: string;
  brand?: string;
};

export const defaultProps: HydraClipProps = {
  title: "Your video title",
  subtitle: "Made with HydraClip",
  scenes: [
    { text: "This is the hook." },
    { text: "Here is the main point." },
    { text: "Follow for more." },
  ],
  audioSrc: null,
  durationSeconds: 15,
  accent: "#ffd166",
  backgroundStart: "#071a3a",
  backgroundEnd: "#6a1b9a",
  brand: "HYDRACLIP",
};

const FPS = 30;

export const calculateMetadata = ({
  props,
}: {
  props: HydraClipProps;
}): { durationInFrames: number; fps: number } => {
  const seconds = Math.min(180, Math.max(5, props.durationSeconds ?? 20));
  return { durationInFrames: Math.round(seconds * FPS), fps: FPS };
};

const SceneCard: React.FC<{
  scene: Scene;
  index: number;
  durationInFrames: number;
  accent: string;
  backgroundStart: string;
  backgroundEnd: string;
}> = ({
  scene,
  index,
  durationInFrames,
  accent,
  backgroundStart,
  backgroundEnd,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const [imageFailed, setImageFailed] = useState(false);

  const enter = spring({
    frame,
    fps,
    config: { damping: 200, mass: 0.8 },
    durationInFrames: 18,
  });
  const exit = interpolate(
    frame,
    [Math.max(1, durationInFrames - 14), Math.max(2, durationInFrames - 2)],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const opacity = Math.min(enter, exit);
  const translateY = interpolate(enter, [0, 1], [70, 0]);
  const scale = interpolate(enter, [0, 1], [0.92, 1]);

  // Alternating Ken Burns direction keeps consecutive photos from feeling static.
  const direction = index % 2 === 0 ? 1 : -1;
  const imageScale = interpolate(
    frame,
    [0, Math.max(1, durationInFrames)],
    [1.06, 1.2],
    { extrapolateRight: "clamp" },
  );
  const imageTranslateX = interpolate(
    frame,
    [0, Math.max(1, durationInFrames)],
    [-16 * direction, 16 * direction],
    { extrapolateRight: "clamp" },
  );
  const imageTranslateY = interpolate(
    frame,
    [0, Math.max(1, durationInFrames)],
    [-12, 12],
    { extrapolateRight: "clamp" },
  );

  const text = scene.text ?? "";
  const fontSize =
    text.length > 90 ? 62 : text.length > 55 ? 76 : text.length > 28 ? 94 : 110;
  const hasImage = Boolean(scene.image) && !imageFailed;

  return (
    <AbsoluteFill style={{ opacity }}>
      {hasImage ? (
        <AbsoluteFill style={{ overflow: "hidden", backgroundColor: "#04070f" }}>
          <Img
            src={scene.image as string}
            onError={() => setImageFailed(true)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              transform: `scale(${imageScale}) translate(${imageTranslateX}px, ${imageTranslateY}px)`,
            }}
          />
          <AbsoluteFill
            style={{
              background:
                "linear-gradient(180deg, rgba(4,7,15,0.82) 0%, rgba(4,7,15,0.38) 32%, rgba(4,7,15,0.58) 68%, rgba(4,7,15,0.94) 100%)",
            }}
          />
        </AbsoluteFill>
      ) : (
        <AbsoluteFill
          style={{
            background: `linear-gradient(135deg, ${backgroundStart} 0%, ${backgroundEnd} 100%)`,
          }}
        >
          <div
            style={{
              position: "absolute",
              top: -220,
              left: -180 + (index % 2) * 260,
              width: 900,
              height: 900,
              borderRadius: "50%",
              background: `radial-gradient(circle, ${accent}44 0%, ${accent}11 38%, transparent 70%)`,
            }}
          />
        </AbsoluteFill>
      )}

      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          padding: "0 90px",
        }}
      >
        <div
          style={{
            transform: `translateY(${translateY}px) scale(${scale})`,
            textAlign: "center",
            maxWidth: 900,
          }}
        >
          <div
            style={{
              width: 110,
              height: 10,
              borderRadius: 5,
              background: scene.accent || accent,
              margin: "0 auto 42px",
            }}
          />
          <div
            style={{
              fontSize,
              lineHeight: 1.12,
              fontWeight: 800,
              color: "#ffffff",
              letterSpacing: "-1.5px",
              textShadow: "0 6px 26px rgba(0,0,0,0.75)",
              fontFamily: "DejaVu Sans, Arial, sans-serif",
              overflowWrap: "break-word",
            }}
          >
            {text}
          </div>
        </div>
      </AbsoluteFill>

      {/* Vignette keeps the edges quiet and the text readable over busy photos. */}
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(circle at 50% 45%, transparent 30%, rgba(0,0,0,0.42) 100%)",
        }}
      />
    </AbsoluteFill>
  );
};

export const HydraClipShort: React.FC<HydraClipProps> = (props) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  const scenes =
    Array.isArray(props.scenes) && props.scenes.length > 0
      ? props.scenes
      : defaultProps.scenes;
  const accent = props.accent || defaultProps.accent!;
  const backgroundStart =
    props.backgroundStart || defaultProps.backgroundStart!;
  const backgroundEnd = props.backgroundEnd || defaultProps.backgroundEnd!;

  // Split the composition evenly across scenes. The last scene absorbs the
  // remainder so the total always matches durationInFrames exactly.
  const base = Math.max(1, Math.floor(durationInFrames / scenes.length));
  const timed = scenes.map((scene, index) => {
    const from = index * base;
    const frames =
      index === scenes.length - 1 ? durationInFrames - from : base;
    return {
      scene,
      index,
      from,
      durationInFrames: Math.max(1, frames),
    };
  });

  const glowX = interpolate(
    frame,
    [0, Math.max(1, durationInFrames)],
    [-240, 1200],
    { extrapolateRight: "clamp" },
  );
  const progress = interpolate(
    frame,
    [0, Math.max(1, durationInFrames - 1)],
    [0, 100],
    { extrapolateRight: "clamp" },
  );
  const activeScene =
    Math.min(
      scenes.length,
      Math.floor((frame / Math.max(1, durationInFrames)) * scenes.length) + 1,
    ) || 1;

  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(135deg, ${backgroundStart} 0%, ${backgroundEnd} 100%)`,
        fontFamily: "DejaVu Sans, Arial, sans-serif",
      }}
    >
      {props.audioSrc ? <Audio src={props.audioSrc} /> : null}

      <div
        style={{
          position: "absolute",
          top: -220,
          left: glowX,
          width: 900,
          height: 900,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${accent}33 0%, ${accent}0d 38%, transparent 70%)`,
        }}
      />

      {timed.map((item) => (
        <Sequence
          key={item.index}
          from={item.from}
          durationInFrames={item.durationInFrames}
        >
          <SceneCard
            scene={item.scene}
            index={item.index}
            durationInFrames={item.durationInFrames}
            accent={accent}
            backgroundStart={backgroundStart}
            backgroundEnd={backgroundEnd}
          />
        </Sequence>
      ))}

      {/* Header and footer sit above the scene imagery. */}
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(180deg, rgba(4,7,15,0.9) 0%, transparent 18%, transparent 82%, rgba(4,7,15,0.92) 100%)",
        }}
      />

      <div
        style={{
          position: "absolute",
          top: 70,
          left: 78,
          right: 78,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div
          style={{
            padding: "12px 22px",
            borderRadius: 999,
            background: "rgba(255,255,255,0.12)",
            color: "#ffffff",
            fontSize: 24,
            fontWeight: 700,
            letterSpacing: 3,
          }}
        >
          {props.brand || "HYDRACLIP"}
        </div>
        <div
          style={{
            color: "rgba(255,255,255,0.7)",
            fontSize: 24,
            fontWeight: 600,
            textShadow: "0 2px 8px rgba(0,0,0,0.6)",
          }}
        >
          {String(activeScene).padStart(2, "0")} /{" "}
          {String(scenes.length).padStart(2, "0")}
        </div>
      </div>

      <div
        style={{
          position: "absolute",
          top: 150,
          left: 90,
          right: 90,
          textAlign: "center",
          color: "#ffffff",
          fontSize: 42,
          fontWeight: 600,
          opacity: 0.95,
          lineHeight: 1.15,
          textShadow: "0 4px 18px rgba(0,0,0,0.7)",
        }}
      >
        {props.title}
      </div>

      {scenes[activeScene - 1]?.credit ? (
        <div
          style={{
            position: "absolute",
            bottom: 138,
            left: 90,
            right: 90,
            textAlign: "center",
            fontSize: 18,
            color: "rgba(255,255,255,0.55)",
            textShadow: "0 2px 8px rgba(0,0,0,0.8)",
          }}
        >
          {scenes[activeScene - 1].credit}
        </div>
      ) : null}

      <div
        style={{
          position: "absolute",
          bottom: 80,
          left: 90,
          right: 90,
        }}
      >
        <div
          style={{
            height: 8,
            borderRadius: 4,
            background: "rgba(255,255,255,0.18)",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              height: "100%",
              width: `${progress}%`,
              background: accent,
              borderRadius: 4,
            }}
          />
        </div>
        <div
          style={{
            marginTop: 20,
            color: "rgba(255,255,255,0.6)",
            fontSize: 24,
            textAlign: "center",
            textShadow: "0 2px 8px rgba(0,0,0,0.6)",
          }}
        >
          {props.subtitle || ""}
        </div>
      </div>
    </AbsoluteFill>
  );
};

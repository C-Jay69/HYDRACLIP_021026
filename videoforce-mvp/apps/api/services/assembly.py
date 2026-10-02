"""Video assembly: script in, finished MP4 out.

No frames are generated. The video is built from stock footage that already
exists, narrated with synthesised speech, and captioned from the narration
text. The pipeline is:

1. **Plan** -- split the script into scenes, one per sentence or two, and
   derive a visual search query for each from its own keywords.
2. **Narrate** -- synthesise each scene's audio separately and measure it.
   Scene durations come from the real audio, so picture and voice cannot
   drift apart; this is also what makes subtitle timings exact.
3. **Source** -- find footage for each scene, preferring video clips and
   falling back to stills. Assets already used are excluded so a short video
   does not show the same clip three times.
4. **Build** -- render each scene to an identically-encoded clip of exactly
   the right length: clips are looped or trimmed, stills get a slow Ken
   Burns push so the frame is never completely static.
5. **Join** -- concatenate the clips, lay the narration over them, burn in
   the captions, and write the MP4.

Every step is skippable in the sense that a missing dependency produces an
explanation rather than a traceback. ``unavailable_reason`` reports all of
them at once.
"""

from __future__ import annotations

import logging
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable, Sequence

from apps.api.core.config import settings
from apps.api.services import subtitles as subs
from apps.api.services.media import (
    MediaToolError,
    ffmpeg_unavailable_reason,
    is_still_image,
    probe_duration,
    run_ffmpeg,
)
from apps.api.services.stock import (
    IMAGE,
    VIDEO,
    StockAsset,
    StockError,
    StockLibrary,
    get_stock_library,
)

logger = logging.getLogger(__name__)


class AssemblyError(RuntimeError):
    """Assembly failed for a reportable reason."""


class AssemblyUnavailable(AssemblyError):
    """Assembly cannot run because a dependency is missing."""


# Words that make terrible image search queries.
_STOPWORDS = frozenset(
    """
    a an and are as at be been but by can could did do does for from had has have
    he her here his how i if in into is it its just like me more most my no not of
    off on once only or our out over own she should so some such than that the
    their them then there these they this those through to too under until up very
    was we were what when where which while who why will with would you your about
    after again all also am any because before being below between both down during
    each few further having if other same too was what
    """.split()
)

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]+")


@dataclass
class Scene:
    """One beat of the video."""

    index: int
    text: str
    query: str
    duration: float = 0.0
    start: float = 0.0
    audio_path: Path | None = None
    asset: StockAsset | None = None
    clip_path: Path | None = None

    @property
    def key(self) -> str:
        return f"{self.asset.provider}:{self.asset.asset_id}" if self.asset else ""


@dataclass
class RenderResult:
    """What a completed render produced."""

    video_path: Path
    duration: float
    width: int
    height: int
    scenes: list[Scene] = field(default_factory=list)
    subtitle_path: Path | None = None
    credits: list[dict] = field(default_factory=list)
    #: True when any asset came from a watermarked preview, which makes the
    #: output a draft rather than something publishable.
    draft: bool = False
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> dict:
        return {
            "duration_seconds": round(self.duration, 2),
            "width": self.width,
            "height": self.height,
            "scene_count": len(self.scenes),
            "has_subtitles": self.subtitle_path is not None,
            "draft": self.draft,
            "credits": self.credits,
            "warnings": self.warnings,
            "sources": sorted({c["provider"] for c in self.credits}),
        }


# ---------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------


def derive_query(text: str, topic: str = "") -> str:
    """Turn a sentence into a stock search query.

    Deliberately crude: pick the longest few non-stopword words, which in
    practice are the concrete nouns, and fall back to the overall topic when
    a sentence is all filler ("And that's why it matters."). An LLM could do
    better, but this runs in microseconds and never fails.
    """
    words = [w.lower() for w in _WORD_RE.findall(text or "")]
    keywords = [w for w in words if w not in _STOPWORDS and len(w) > 3]

    # Longest-first approximates specificity, then restore reading order so
    # the query still looks like a phrase.
    ranked = sorted(set(keywords), key=lambda w: (-len(w), words.index(w)))[:3]
    ordered = sorted(ranked, key=lambda w: words.index(w))

    query = " ".join(ordered)
    if not query:
        query = (topic or "abstract background").strip()
    return query[:100]


def plan_scenes(
    script: str,
    topic: str = "",
    max_scenes: int = 24,
) -> list[Scene]:
    """Split a script into scenes.

    One sentence per scene, except that very short sentences are merged into
    the next one -- a two-word sentence does not deserve its own clip, and a
    sub-second cut reads as a glitch.
    """
    sentences = subs.split_sentences(script)
    if not sentences:
        raise AssemblyError("The script is empty, so there is nothing to assemble.")

    merged: list[str] = []
    for sentence in sentences:
        if merged and len(merged[-1]) < 40:
            merged[-1] = f"{merged[-1]} {sentence}"
        else:
            merged.append(sentence)

    if len(merged) > max_scenes:
        # Fold the tail into the last allowed scene rather than truncating
        # narration, which would silently drop words from the script.
        head = merged[: max_scenes - 1]
        tail = " ".join(merged[max_scenes - 1 :])
        merged = head + [tail]

    return [
        Scene(index=i, text=text, query=derive_query(text, topic))
        for i, text in enumerate(merged)
    ]


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

#: Signature of the narration callable: (text, output_path) -> path.
Synthesiser = Callable[[str, str], Awaitable[str]]


class VideoAssembler:
    """Builds an MP4 from a script, stock footage and narration."""

    def __init__(
        self,
        library: StockLibrary | None = None,
        synthesiser: Synthesiser | None = None,
        work_dir: Path | None = None,
    ) -> None:
        self.library = library or get_stock_library()
        self.synthesiser = synthesiser
        self.work_dir = Path(work_dir or settings.MEDIA_WORK_DIR)
        self.width = settings.VIDEO_WIDTH
        self.height = settings.VIDEO_HEIGHT
        self.fps = settings.VIDEO_FPS

    # --- Readiness -----------------------------------------------------------

    def unavailable_reason(self) -> str | None:
        """Every missing dependency at once, or None when ready."""
        problems = []

        ffmpeg_problem = ffmpeg_unavailable_reason()
        if ffmpeg_problem:
            problems.append(ffmpeg_problem)

        stock_problem = self.library.unavailable_reason()
        if stock_problem:
            problems.append(stock_problem)

        if self.synthesiser is None:
            problems.append("No speech synthesiser was supplied for narration.")

        return " ".join(problems) if problems else None

    # --- Entry point ---------------------------------------------------------

    async def render(
        self,
        script: str,
        topic: str = "",
        output_path: str | Path | None = None,
        burn_subtitles: bool | None = None,
        on_progress: Callable[[str, float], None] | None = None,
    ) -> RenderResult:
        problem = self.unavailable_reason()
        if problem:
            raise AssemblyUnavailable(problem)

        burn = settings.SUBTITLES_ENABLED if burn_subtitles is None else burn_subtitles

        job_dir = Path(self.work_dir) / f"render_{_token()}"
        job_dir.mkdir(parents=True, exist_ok=True)

        def progress(stage: str, fraction: float) -> None:
            if on_progress:
                try:
                    on_progress(stage, fraction)
                except Exception:  # noqa: BLE001
                    logger.debug("Progress callback raised; ignoring.", exc_info=True)

        warnings: list[str] = []

        try:
            scenes = plan_scenes(script, topic)
            progress("planned", 0.05)

            await self._narrate(scenes, job_dir)
            progress("narrated", 0.30)

            warnings += await self._source(scenes, job_dir, topic)
            progress("sourced", 0.55)

            self._build_clips(scenes, job_dir)
            progress("clips", 0.75)

            srt_path = self._write_subtitles(scenes, job_dir) if burn else None

            final = Path(output_path) if output_path else job_dir / "output.mp4"
            self._join(scenes, job_dir, final, srt_path)
            progress("muxed", 0.95)

            duration = probe_duration(final)
            credits = [s.asset.to_dict() for s in scenes if s.asset]
            draft = any(s.asset.watermarked for s in scenes if s.asset)

            if draft:
                warnings.append(
                    "At least one clip is a watermarked preview, so this render "
                    "is a draft and must not be published."
                )

            progress("done", 1.0)
            return RenderResult(
                video_path=final,
                duration=duration,
                width=self.width,
                height=self.height,
                scenes=scenes,
                subtitle_path=srt_path,
                credits=credits,
                draft=draft,
                warnings=warnings,
            )
        except (MediaToolError, StockError) as exc:
            raise AssemblyError(str(exc)) from exc

    # --- Stages --------------------------------------------------------------

    async def _narrate(self, scenes: list[Scene], job_dir: Path) -> None:
        """Synthesise each scene and measure what came back."""
        assert self.synthesiser is not None

        cursor = 0.0
        for scene in scenes:
            target = job_dir / f"scene_{scene.index:03d}.wav"
            produced = await self.synthesiser(scene.text, str(target))
            path = Path(produced or target)

            if not path.exists() or path.stat().st_size == 0:
                raise AssemblyError(
                    f"Narration for scene {scene.index + 1} produced no audio."
                )

            measured = probe_duration(path)
            # Guard against a synthesiser returning a near-empty clip: a
            # 0.4s scene reads as a flicker.
            scene.duration = max(measured, settings.SCENE_MIN_SECONDS)
            scene.start = cursor
            cursor += scene.duration

            # Normalise every segment to exactly its scene length. This is
            # not cosmetic. Whenever the clamp above stretches a scene past
            # its narration, the picture is longer than the sound; without
            # padding, the audio track ends up shorter than the video track,
            # -shortest truncates the result, and every subtitle after the
            # first clamped scene drifts by the accumulated difference.
            # Fixing the length here keeps picture, sound and captions on a
            # single timeline. Re-encoding to one format also makes the
            # concat demuxer safe, since it requires identical inputs.
            scene.audio_path = self._fit_audio(path, scene.duration)

    def _fit_audio(self, source: Path, duration: float) -> Path:
        """Pad or trim narration to exactly ``duration``, in one format."""
        output = source.with_name(f"{source.stem}_fit.wav")
        run_ffmpeg(
            [
                "-i",
                str(source),
                # apad appends silence indefinitely; -t decides where to stop,
                # so this both pads short audio and trims long audio.
                "-af",
                "apad",
                "-t",
                f"{duration:.3f}",
                "-ar",
                "44100",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                "-y",
                str(output),
            ]
        )
        return output

    async def _source(
        self, scenes: list[Scene], job_dir: Path, topic: str
    ) -> list[str]:
        """Find and download footage, avoiding repeats."""
        warnings: list[str] = []
        used: set[str] = set()
        media_dir = job_dir / "media"
        media_dir.mkdir(parents=True, exist_ok=True)

        for scene in scenes:
            asset = await self._pick_asset(scene, used, topic)
            if asset is None:
                warnings.append(
                    f"No footage matched scene {scene.index + 1} "
                    f"({scene.query!r}); it will use a plain background."
                )
                continue

            suffix = ".mp4" if asset.kind == VIDEO else ".jpg"
            destination = media_dir / f"asset_{scene.index:03d}{suffix}"
            try:
                await self.library.download(asset, destination)
            except StockError as exc:
                warnings.append(
                    f"Could not download footage for scene {scene.index + 1}: {exc}"
                )
                continue

            scene.asset = asset
            scene.clip_path = destination
            used.add(scene.key)

        if not any(s.clip_path for s in scenes):
            raise AssemblyError(
                "No footage could be sourced for any scene, so there is nothing "
                "to show. Check the stock provider API keys and the search terms."
            )

        return warnings

    async def _pick_asset(
        self, scene: Scene, used: set[str], topic: str
    ) -> StockAsset | None:
        """Best unused asset for a scene, widening the search if needed."""
        queries = [scene.query]
        if topic and topic.lower() not in scene.query.lower():
            queries.append(topic)

        for query in queries:
            try:
                candidates = await self.library.find(
                    query,
                    prefer_video=True,
                    orientation="vertical",
                    limit=12,
                    exclude_ids=used,
                )
            except StockError as exc:
                logger.warning("Sourcing failed for %r: %s", query, exc)
                continue

            for candidate in candidates:
                if f"{candidate.provider}:{candidate.asset_id}" not in used:
                    return candidate

        return None

    def _build_clips(self, scenes: list[Scene], job_dir: Path) -> None:
        """Render every scene to an identically-encoded clip.

        Encoding each scene the same way is what lets the final concatenation
        use stream copy instead of a second full re-encode.
        """
        clips_dir = job_dir / "clips"
        clips_dir.mkdir(parents=True, exist_ok=True)

        for scene in scenes:
            output = clips_dir / f"clip_{scene.index:03d}.mp4"

            if scene.clip_path is None:
                self._render_placeholder(scene, output)
                scene.clip_path = output
                continue

            # Trust the bytes over the metadata. A provider that labels a
            # still as a clip (or serves an extensionless URL) would
            # otherwise fail deep inside ffmpeg with "Option loop not
            # found", which explains nothing about the real problem.
            try:
                still = is_still_image(scene.clip_path)
            except MediaToolError:
                still = bool(scene.asset and scene.asset.kind == IMAGE)

            if still:
                self._render_still(scene, output)
            else:
                self._render_motion(scene, output)

            scene.clip_path = output

    def _encode_args(self) -> list[str]:
        """Shared encoder settings. Identical across every scene clip."""
        return [
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(self.fps),
            # A closed GOP at the cut point keeps concatenation clean.
            "-g",
            str(self.fps * 2),
            "-an",
        ]

    @property
    def _fit_filter(self) -> str:
        """Scale to cover the frame, centre-crop the overflow, square pixels."""
        return (
            f"scale={self.width}:{self.height}:force_original_aspect_ratio=increase,"
            f"crop={self.width}:{self.height},setsar=1"
        )

    def _render_motion(self, scene: Scene, output: Path) -> None:
        """A stock clip, looped or trimmed to the scene's exact length."""
        run_ffmpeg(
            [
                # Loop the input so a 4s clip can fill an 11s scene. -t on the
                # output stops it; without the loop ffmpeg would end early and
                # the audio would run over black.
                "-stream_loop",
                "-1",
                "-i",
                str(scene.clip_path),
                "-t",
                f"{scene.duration:.3f}",
                "-vf",
                f"{self._fit_filter},fps={self.fps}",
                *self._encode_args(),
                "-y",
                str(output),
            ]
        )

    def _render_still(self, scene: Scene, output: Path) -> None:
        """A photo with a slow Ken Burns push.

        zoompan works on frames, not seconds, so the zoom is spread across
        ``duration * fps`` frames. Scaling up by 4x first is the standard
        workaround for zoompan's jittery subpixel stepping at native size.
        """
        frames = max(1, int(round(scene.duration * self.fps)))
        zoom_step = 0.0015

        filtergraph = (
            f"scale={self.width * 4}:{self.height * 4}"
            f":force_original_aspect_ratio=increase,"
            f"crop={self.width * 4}:{self.height * 4},"
            f"zoompan=z='min(zoom+{zoom_step},1.25)'"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d={frames}:s={self.width}x{self.height}:fps={self.fps},"
            f"setsar=1"
        )

        run_ffmpeg(
            [
                "-loop",
                "1",
                "-i",
                str(scene.clip_path),
                "-t",
                f"{scene.duration:.3f}",
                "-vf",
                filtergraph,
                *self._encode_args(),
                "-y",
                str(output),
            ]
        )

    def _render_placeholder(self, scene: Scene, output: Path) -> None:
        """A plain gradient, when nothing could be sourced for a scene.

        Better than aborting the whole render over one unmatched sentence --
        the narration and captions still carry the content.
        """
        run_ffmpeg(
            [
                "-f",
                "lavfi",
                "-i",
                f"color=c=0x101828:s={self.width}x{self.height}:r={self.fps}",
                "-t",
                f"{scene.duration:.3f}",
                "-vf",
                "setsar=1",
                *self._encode_args(),
                "-y",
                str(output),
            ]
        )

    def _write_subtitles(self, scenes: list[Scene], job_dir: Path) -> Path:
        """Write both caption formats and return the SRT sidecar.

        The ASS file is what gets burned in, because it can declare the
        video's real resolution. The SRT is kept because it is the format
        YouTube, TikTok and every editor accept as an upload, and shipping
        it costs nothing.
        """
        segments = [(s.text, s.start, s.duration) for s in scenes]
        cues = subs.build_cues(segments)

        srt_path = job_dir / "captions.srt"
        srt_path.write_text(subs.to_srt(cues), encoding="utf-8")

        ass_path = job_dir / "captions.ass"
        ass_path.write_text(
            subs.to_ass(
                cues,
                width=self.width,
                height=self.height,
                font_size=settings.SUBTITLE_FONT_SIZE,
            ),
            encoding="utf-8",
        )
        return srt_path

    def _join(
        self,
        scenes: list[Scene],
        job_dir: Path,
        output: Path,
        srt_path: Path | None,
    ) -> None:
        """Concatenate clips, attach narration, burn captions."""
        video_track = job_dir / "video_track.mp4"
        audio_track = job_dir / "audio_track.m4a"

        self._concat([s.clip_path for s in scenes if s.clip_path], video_track, "v")
        self._concat([s.audio_path for s in scenes if s.audio_path], audio_track, "a")

        args = ["-i", str(video_track), "-i", str(audio_track)]

        if srt_path is not None:
            # Burn the ASS rather than the SRT: it carries the frame
            # resolution, so the font size and margin written in
            # _write_subtitles are the ones that actually appear.
            ass_path = srt_path.with_suffix(".ass")
            escaped = subs.escape_for_filter(str(ass_path))
            args += ["-vf", f"ass='{escaped}'"]
            args += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23"]
            args += ["-pix_fmt", "yuv420p"]
        else:
            # Nothing to draw, so the video track survives untouched.
            args += ["-c:v", "copy"]

        args += [
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-ar",
            "44100",
            # Stop at whichever track ends first so a rounding difference
            # cannot leave a frozen frame or silent tail.
            "-shortest",
            "-movflags",
            "+faststart",
            "-y",
            str(output),
        ]

        output.parent.mkdir(parents=True, exist_ok=True)
        run_ffmpeg(args)

    def _concat(self, parts: Sequence[Path | None], output: Path, kind: str) -> None:
        """Concatenate same-format parts via the concat demuxer.

        The list file lives in the job directory, not at a fixed path --
        ``/tmp/ffmpeg_concat_list.txt`` would be overwritten by any other
        render running at the same time.
        """
        paths = [p for p in parts if p is not None]
        if not paths:
            raise AssemblyError(f"No {kind} segments to concatenate.")

        if len(paths) == 1 and kind == "v":
            shutil.copyfile(paths[0], output)
            return

        list_file = output.parent / f"{output.stem}_concat.txt"
        list_file.write_text(
            "\n".join(f"file '{Path(p).resolve()}'" for p in paths) + "\n",
            encoding="utf-8",
        )

        args = ["-f", "concat", "-safe", "0", "-i", str(list_file)]
        if kind == "v":
            # Every clip was encoded with identical settings, so copying is
            # safe here and avoids a generation of quality loss.
            args += ["-c", "copy"]
        else:
            # Narration segments are whatever the synthesiser emitted, so
            # normalise them into one AAC track.
            args += ["-c:a", "aac", "-b:a", "160k", "-ar", "44100"]
        args += ["-y", str(output)]

        run_ffmpeg(args)


def _token() -> str:
    import uuid

    return uuid.uuid4().hex[:12]


_assembler: VideoAssembler | None = None


def get_assembler(synthesiser: Synthesiser | None = None) -> VideoAssembler:
    """Shared assembler instance."""
    global _assembler
    if _assembler is None or synthesiser is not None:
        _assembler = VideoAssembler(synthesiser=synthesiser)
    return _assembler

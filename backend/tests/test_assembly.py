"""Video assembly.

The planning and readiness logic is tested directly. The render itself is
tested end to end against real ffmpeg, using synthetic source media and a
synthetic narrator: the assembler only ever consumes *measured* durations
and local files, so generated fixtures exercise exactly the same code path
real stock footage would. Those tests skip when ffmpeg is absent.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from apps.api.core.config import settings
from apps.api.services import media
from apps.api.services.assembly import (
    AssemblyError,
    AssemblyUnavailable,
    Scene,
    VideoAssembler,
    derive_query,
    plan_scenes,
)
from apps.api.services.stock import IMAGE, VIDEO, StockAsset, StockLibrary

SCRIPT = (
    "Ocean plastic is choking marine ecosystems worldwide. "
    "Every single year, eleven million tonnes enter the sea. "
    "Floating debris traps turtles, seabirds and dolphins. "
    "But coastal cleanup projects are finally reversing the damage."
)


def ffmpeg_or_skip() -> str:
    reason = media.ffmpeg_unavailable_reason()
    if reason:
        pytest.skip(f"ffmpeg is unavailable: {reason}")
    return media.ffmpeg_path()


# --- Planning -----------------------------------------------------------------


def test_each_sentence_becomes_a_scene():
    scenes = plan_scenes(SCRIPT, topic="ocean plastic")
    assert len(scenes) == 4
    assert scenes[0].text.startswith("Ocean plastic")
    assert [s.index for s in scenes] == [0, 1, 2, 3]


def test_short_sentences_merge_into_their_neighbour():
    """A two-word scene would be a sub-second flicker."""
    scenes = plan_scenes("Wait. Here is a much longer sentence to merge into.")
    assert len(scenes) == 1
    assert scenes[0].text.startswith("Wait.")


def test_an_empty_script_is_refused():
    with pytest.raises(AssemblyError, match="empty"):
        plan_scenes("   ")


def test_scene_count_is_capped_without_dropping_narration():
    script = " ".join(f"This is sentence number {i} of the script." for i in range(40))
    scenes = plan_scenes(script, max_scenes=5)

    assert len(scenes) == 5
    # Every word still appears somewhere; truncating would silently mute text.
    assert "number 39" in " ".join(s.text for s in scenes)


def test_queries_drop_filler_words():
    query = derive_query("And so it is that the plastic reaches the ocean floor.")
    assert "the" not in query.split()
    assert "and" not in query.split()
    assert "plastic" in query or "reaches" in query


def test_a_filler_only_sentence_falls_back_to_the_topic():
    assert derive_query("And so it was.", topic="ocean plastic") == "ocean plastic"


def test_query_length_is_capped_for_pixabay():
    long_sentence = " ".join(f"extraordinarily{i}" for i in range(40))
    assert len(derive_query(long_sentence)) <= 100


# --- Readiness ----------------------------------------------------------------


def test_missing_dependencies_are_reported_together(monkeypatch):
    """Discovering missing pieces one failed job at a time is miserable."""
    for key in (
        "PEXELS_API_KEY",
        "PIXABAY_API_KEY",
        "UNSPLASH_ACCESS_KEY",
        "SHUTTERSTOCK_API_TOKEN",
    ):
        monkeypatch.setattr(settings, key, "")

    assembler = VideoAssembler(library=StockLibrary(), synthesiser=None)
    reason = assembler.unavailable_reason()

    assert reason is not None
    assert "PEXELS_API_KEY" in reason
    assert "synthesiser" in reason


async def test_render_refuses_when_a_dependency_is_missing(monkeypatch):
    monkeypatch.setattr(settings, "PEXELS_API_KEY", "")
    monkeypatch.setattr(settings, "PIXABAY_API_KEY", "")
    monkeypatch.setattr(settings, "UNSPLASH_ACCESS_KEY", "")
    monkeypatch.setattr(settings, "SHUTTERSTOCK_API_TOKEN", "")

    assembler = VideoAssembler(library=StockLibrary(), synthesiser=None)

    with pytest.raises(AssemblyUnavailable):
        await assembler.render(SCRIPT)


def test_ready_when_ffmpeg_and_one_provider_exist(monkeypatch):
    ffmpeg_or_skip()
    monkeypatch.setattr(settings, "PEXELS_API_KEY", "key")

    async def synth(text, destination):
        return destination

    assembler = VideoAssembler(library=StockLibrary(), synthesiser=synth)
    assert assembler.unavailable_reason() is None


# --- End-to-end rendering -----------------------------------------------------


@pytest.fixture
def source_media(tmp_path):
    """Synthetic stock: a landscape clip, a short clip, and a tall still.

    The landscape sources matter -- they prove the fit filter crops 16:9
    footage into a 9:16 frame instead of letterboxing it.
    """
    ffmpeg = ffmpeg_or_skip()
    media_dir = tmp_path / "source"
    media_dir.mkdir()

    wide = media_dir / "wide.mp4"
    short = media_dir / "short.mp4"
    still = media_dir / "still.jpg"

    subprocess.run(
        [ffmpeg, "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", "testsrc2=size=1920x1080:rate=25:duration=4",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(wide)],
        check=True,
    )
    subprocess.run(
        [ffmpeg, "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", "smptebars=size=1280x720:rate=25:duration=2",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(short)],
        check=True,
    )
    subprocess.run(
        [ffmpeg, "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", "gradients=size=1500x2000:duration=1", "-frames:v", "1", str(still)],
        check=True,
    )
    return [(wide, VIDEO), (short, VIDEO), (still, IMAGE)]


class LocalLibrary(StockLibrary):
    """A StockLibrary backed by local files instead of the network."""

    def __init__(self, sources):
        super().__init__(providers=[])
        self.sources = sources
        self.calls = 0
        self.queries: list[str] = []

    def available(self):
        return ["local"]

    def unavailable_reason(self):
        return None

    async def find(
        self, query, prefer_video=True, orientation="vertical", limit=10,
        exclude_ids=None,
    ):
        self.queries.append(query)
        path, kind = self.sources[self.calls % len(self.sources)]
        self.calls += 1
        return [
            StockAsset(
                provider="pexels",
                asset_id=f"local-{self.calls}",
                kind=kind,
                url=str(path),
                width=1080,
                height=1920,
                page_url="https://www.pexels.com/video/x",
                author="Test Photographer",
                license_note="Pexels License",
            )
        ]

    async def download(self, asset, destination):
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(asset.url, destination)
        return destination


def make_narrator(ffmpeg: str, seconds: float | None = None):
    """A stand-in narrator emitting a tone of a plausible length.

    No Piper voice model is downloadable in this environment, and it does
    not matter: the assembler consumes the *measured* duration of whatever
    audio it is handed, so a tone exercises the identical code path.
    """

    async def narrate(text: str, destination: str) -> str:
        length = seconds if seconds is not None else max(1.5, min(len(text) / 15.0, 8.0))
        subprocess.run(
            [ffmpeg, "-y", "-loglevel", "error", "-f", "lavfi",
             "-i", f"sine=frequency=220:duration={length:.2f}",
             "-ar", "22050", "-ac", "1", destination],
            check=True,
        )
        return destination

    return narrate


async def test_render_produces_a_playable_vertical_mp4(tmp_path, source_media):
    ffmpeg = ffmpeg_or_skip()
    library = LocalLibrary(source_media)

    assembler = VideoAssembler(
        library=library,
        synthesiser=make_narrator(ffmpeg),
        work_dir=tmp_path / "work",
    )
    output = tmp_path / "out.mp4"
    result = await assembler.render(SCRIPT, topic="ocean plastic", output_path=output)

    assert output.exists() and output.stat().st_size > 10_000
    assert result.width == 1080 and result.height == 1920
    assert len(result.scenes) == 4

    # ffmpeg must agree the file has both streams at the right size.
    probe = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(output)],
        capture_output=True, text=True,
    ).stderr
    assert "1080x1920" in probe
    assert "Video: h264" in probe
    assert "Audio: aac" in probe


async def test_rendered_duration_matches_the_narration(tmp_path, source_media):
    """Picture, sound and captions must share one timeline."""
    ffmpeg = ffmpeg_or_skip()
    assembler = VideoAssembler(
        library=LocalLibrary(source_media),
        synthesiser=make_narrator(ffmpeg),
        work_dir=tmp_path / "work",
    )
    output = tmp_path / "out.mp4"
    result = await assembler.render(SCRIPT, output_path=output)

    expected = sum(s.duration for s in result.scenes)
    # Within one frame at 30fps.
    assert abs(result.duration - expected) < 0.05


async def test_short_narration_is_padded_rather_than_truncating_the_video(
    tmp_path, source_media
):
    """A scene clamped to the minimum must still have audio under it.

    Without padding the audio track ends short, -shortest truncates the
    render, and every later caption drifts.
    """
    ffmpeg = ffmpeg_or_skip()
    assembler = VideoAssembler(
        library=LocalLibrary(source_media),
        # Far below SCENE_MIN_SECONDS, so every scene gets clamped.
        synthesiser=make_narrator(ffmpeg, seconds=0.4),
        work_dir=tmp_path / "work",
    )
    output = tmp_path / "out.mp4"
    result = await assembler.render(SCRIPT, output_path=output)

    assert all(s.duration == settings.SCENE_MIN_SECONDS for s in result.scenes)
    expected = settings.SCENE_MIN_SECONDS * len(result.scenes)
    assert abs(result.duration - expected) < 0.05


async def test_subtitles_are_written_and_burned(tmp_path, source_media):
    ffmpeg = ffmpeg_or_skip()
    assembler = VideoAssembler(
        library=LocalLibrary(source_media),
        synthesiser=make_narrator(ffmpeg),
        work_dir=tmp_path / "work",
    )
    result = await assembler.render(SCRIPT, output_path=tmp_path / "out.mp4")

    assert result.subtitle_path is not None
    srt = result.subtitle_path.read_text()
    assert "-->" in srt
    assert "Ocean plastic" in srt

    # The ASS sidecar is what actually gets burned in.
    ass = result.subtitle_path.with_suffix(".ass")
    assert ass.exists()
    assert "PlayResY: 1920" in ass.read_text()


async def test_subtitles_can_be_switched_off(tmp_path, source_media):
    ffmpeg = ffmpeg_or_skip()
    assembler = VideoAssembler(
        library=LocalLibrary(source_media),
        synthesiser=make_narrator(ffmpeg),
        work_dir=tmp_path / "work",
    )
    result = await assembler.render(
        SCRIPT, output_path=tmp_path / "out.mp4", burn_subtitles=False
    )

    assert result.subtitle_path is None
    assert result.video_path.exists()


async def test_credits_name_every_source(tmp_path, source_media):
    """Pexels, Pixabay and Unsplash all require attribution."""
    ffmpeg = ffmpeg_or_skip()
    assembler = VideoAssembler(
        library=LocalLibrary(source_media),
        synthesiser=make_narrator(ffmpeg),
        work_dir=tmp_path / "work",
    )
    result = await assembler.render(SCRIPT, output_path=tmp_path / "out.mp4")

    assert len(result.credits) == 4
    assert all(c["credit"] == "Test Photographer / Pexels" for c in result.credits)
    assert result.summary()["sources"] == ["pexels"]


async def test_a_watermarked_source_marks_the_render_as_a_draft(
    tmp_path, source_media
):
    """A Shutterstock comp cannot be published, and the result must say so."""
    ffmpeg = ffmpeg_or_skip()

    class WatermarkedLibrary(LocalLibrary):
        async def find(self, query, **kwargs):
            assets = await super().find(query, **kwargs)
            for asset in assets:
                asset.provider = "shutterstock"
                asset.watermarked = True
            return assets

    assembler = VideoAssembler(
        library=WatermarkedLibrary(source_media),
        synthesiser=make_narrator(ffmpeg),
        work_dir=tmp_path / "work",
    )
    result = await assembler.render(SCRIPT, output_path=tmp_path / "out.mp4")

    assert result.draft is True
    assert any("must not be published" in w for w in result.warnings)


async def test_an_unmatched_scene_falls_back_to_a_placeholder(
    tmp_path, source_media
):
    """One unmatched sentence must not sink the whole render."""
    ffmpeg = ffmpeg_or_skip()

    class PatchyLibrary(LocalLibrary):
        async def find(self, query, **kwargs):
            # Nothing matches the second scene.
            if len(self.queries) == 1:
                self.queries.append(query)
                return []
            return await super().find(query, **kwargs)

    assembler = VideoAssembler(
        library=PatchyLibrary(source_media),
        synthesiser=make_narrator(ffmpeg),
        work_dir=tmp_path / "work",
    )
    result = await assembler.render(SCRIPT, output_path=tmp_path / "out.mp4")

    assert result.video_path.exists()
    assert any("plain background" in w for w in result.warnings)
    assert len(result.credits) == 3


async def test_no_footage_at_all_is_an_error(tmp_path, source_media):
    ffmpeg = ffmpeg_or_skip()

    class EmptyLibrary(LocalLibrary):
        async def find(self, query, **kwargs):
            return []

    assembler = VideoAssembler(
        library=EmptyLibrary(source_media),
        synthesiser=make_narrator(ffmpeg),
        work_dir=tmp_path / "work",
    )

    with pytest.raises(AssemblyError, match="No footage"):
        await assembler.render(SCRIPT, output_path=tmp_path / "out.mp4")


async def test_silent_narration_is_rejected(tmp_path, source_media):
    ffmpeg_or_skip()

    async def produce_nothing(text, destination):
        Path(destination).write_bytes(b"")
        return destination

    assembler = VideoAssembler(
        library=LocalLibrary(source_media),
        synthesiser=produce_nothing,
        work_dir=tmp_path / "work",
    )

    with pytest.raises(AssemblyError, match="no audio"):
        await assembler.render(SCRIPT, output_path=tmp_path / "out.mp4")


async def test_progress_is_reported_in_order(tmp_path, source_media):
    ffmpeg = ffmpeg_or_skip()
    seen: list[tuple[str, float]] = []

    assembler = VideoAssembler(
        library=LocalLibrary(source_media),
        synthesiser=make_narrator(ffmpeg),
        work_dir=tmp_path / "work",
    )
    await assembler.render(
        SCRIPT,
        output_path=tmp_path / "out.mp4",
        on_progress=lambda stage, fraction: seen.append((stage, fraction)),
    )

    assert [s for s, _ in seen] == [
        "planned", "narrated", "sourced", "clips", "muxed", "done",
    ]
    fractions = [f for _, f in seen]
    assert fractions == sorted(fractions)
    assert fractions[-1] == 1.0


async def test_a_raising_progress_callback_does_not_break_the_render(
    tmp_path, source_media
):
    ffmpeg = ffmpeg_or_skip()

    def explode(stage, fraction):
        raise RuntimeError("callback is broken")

    assembler = VideoAssembler(
        library=LocalLibrary(source_media),
        synthesiser=make_narrator(ffmpeg),
        work_dir=tmp_path / "work",
    )
    result = await assembler.render(
        SCRIPT, output_path=tmp_path / "out.mp4", on_progress=explode
    )

    assert result.video_path.exists()


async def test_concurrent_renders_do_not_share_a_concat_list(tmp_path, source_media):
    """The old helper wrote /tmp/ffmpeg_concat_list.txt, so parallel jobs
    spliced each other's clips together."""
    import asyncio

    ffmpeg = ffmpeg_or_skip()

    async def render(index: int):
        assembler = VideoAssembler(
            library=LocalLibrary(source_media),
            synthesiser=make_narrator(ffmpeg),
            work_dir=tmp_path / f"work{index}",
        )
        return await assembler.render(
            SCRIPT, output_path=tmp_path / f"out{index}.mp4"
        )

    first, second = await asyncio.gather(render(1), render(2))

    assert first.video_path != second.video_path
    assert abs(first.duration - second.duration) < 0.05
    assert first.video_path.exists() and second.video_path.exists()


# --- Media helpers ------------------------------------------------------------


def test_duration_probing_works_without_ffprobe(tmp_path, monkeypatch):
    """imageio-ffmpeg ships ffmpeg but not ffprobe, so the fallback matters."""
    ffmpeg = ffmpeg_or_skip()
    clip = tmp_path / "three.mp4"
    subprocess.run(
        [ffmpeg, "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", "testsrc2=size=320x240:rate=25:duration=3",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(clip)],
        check=True,
    )

    monkeypatch.setattr(media, "ffprobe_path", lambda: None)
    assert abs(media.probe_duration(clip) - 3.0) < 0.2


def test_probing_a_missing_file_is_an_error():
    ffmpeg_or_skip()
    with pytest.raises(media.MediaToolError, match="does not exist"):
        media.probe_duration("/nonexistent/file.mp4")


def test_a_failing_ffmpeg_call_reports_its_stderr():
    ffmpeg_or_skip()
    with pytest.raises(media.MediaToolError, match="ffmpeg failed"):
        media.run_ffmpeg(["-i", "/nonexistent/input.mp4", "-y", "/tmp/nope.mp4"])


# --- Watermark ----------------------------------------------------------------


def test_watermark_uses_libass_not_drawtext(tmp_path):
    """drawtext is an optional ffmpeg build flag and is missing from the
    static wheel; libass is already required for captions."""
    from apps.api.services.ai_pipeline import FFmpegProcessor

    ffmpeg = ffmpeg_or_skip()
    source = tmp_path / "in.mp4"
    subprocess.run(
        [ffmpeg, "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", "testsrc2=size=1080x1920:rate=25:duration=1",
         "-f", "lavfi", "-i", "sine=frequency=200:duration=1",
         "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p", str(source)],
        check=True,
    )

    output = tmp_path / "marked.mp4"
    FFmpegProcessor.add_watermark(str(source), str(output), watermark_text="HydraClip")

    assert output.exists() and output.stat().st_size > 0


async def test_watermark_failure_is_not_reported_as_success(
    tmp_path, source_media, monkeypatch
):
    """The stage used to claim success having rendered nothing. A watermark
    that fails must leave `watermarked` false and say so in the warnings."""
    from apps.api.services import ai_pipeline as pipeline_module
    from apps.api.services import assembly as assembly_module

    ffmpeg = ffmpeg_or_skip()

    def explode(*args, **kwargs):
        raise RuntimeError("drawtext is unavailable")

    def tone(self, text, output_path=None):
        subprocess.run(
            [ffmpeg, "-y", "-loglevel", "error", "-f", "lavfi",
             "-i", "sine=frequency=200:duration=2",
             "-ar", "22050", "-ac", "1", output_path],
            check=True,
        )
        return output_path

    monkeypatch.setattr(
        pipeline_module.FFmpegProcessor, "add_watermark", staticmethod(explode)
    )
    monkeypatch.setattr(pipeline_module.settings, "TTS_PROVIDER_ORDER", "piper")
    monkeypatch.setattr(
        pipeline_module.PiperTTS, "availability_error", lambda self: None
    )
    monkeypatch.setattr(pipeline_module.PiperTTS, "synthesize", tone)

    # Point the assembler at local footage instead of a live provider.
    local = LocalLibrary(source_media)
    real_init = assembly_module.VideoAssembler.__init__

    def patched(self, library=None, synthesiser=None, work_dir=None):
        real_init(
            self,
            library=local,
            synthesiser=synthesiser,
            work_dir=work_dir or (tmp_path / "work"),
        )

    monkeypatch.setattr(assembly_module.VideoAssembler, "__init__", patched)

    pipeline = pipeline_module.AIPipeline()
    result = await pipeline.create_video_from_script(
        {"script": SCRIPT, "topic": "ocean"},
        watermark=True,
        output_path=str(tmp_path / "out.mp4"),
    )

    assert result["watermarked"] is False
    assert any("Watermarking failed" in w for w in result["warnings"])
    # The render itself still succeeded.
    assert Path(result["video_path"]).exists()


async def test_a_successful_watermark_is_reported(tmp_path, source_media, monkeypatch):
    from apps.api.services import ai_pipeline as pipeline_module
    from apps.api.services import assembly as assembly_module

    ffmpeg = ffmpeg_or_skip()

    def tone(self, text, output_path=None):
        subprocess.run(
            [ffmpeg, "-y", "-loglevel", "error", "-f", "lavfi",
             "-i", "sine=frequency=200:duration=2",
             "-ar", "22050", "-ac", "1", output_path],
            check=True,
        )
        return output_path

    monkeypatch.setattr(pipeline_module.settings, "TTS_PROVIDER_ORDER", "piper")
    monkeypatch.setattr(
        pipeline_module.PiperTTS, "availability_error", lambda self: None
    )
    monkeypatch.setattr(pipeline_module.PiperTTS, "synthesize", tone)

    local = LocalLibrary(source_media)
    real_init = assembly_module.VideoAssembler.__init__

    def patched(self, library=None, synthesiser=None, work_dir=None):
        real_init(
            self,
            library=local,
            synthesiser=synthesiser,
            work_dir=work_dir or (tmp_path / "work"),
        )

    monkeypatch.setattr(assembly_module.VideoAssembler, "__init__", patched)

    pipeline = pipeline_module.AIPipeline()
    result = await pipeline.create_video_from_script(
        {"script": SCRIPT, "topic": "ocean"},
        watermark=True,
        output_path=str(tmp_path / "out.mp4"),
    )

    assert result["watermarked"] is True
    assert result["warnings"] == []
    assert result["status"] == "rendered"
    assert Path(result["video_path"]).exists()

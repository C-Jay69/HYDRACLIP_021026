"""Locating and driving the ffmpeg binaries.

Two things here are less obvious than they look.

**Finding ffmpeg.** The container installs it with apt, but a developer
checkout often has no system ffmpeg at all. ``imageio-ffmpeg`` ships a static
build as a Python wheel, so if it is installed we fall back to that rather
than failing. The resolved path is cached, because ``shutil.which`` on every
filter call adds up over a few hundred invocations.

**Measuring duration.** ``ffprobe`` is the right tool, but it is a *separate*
binary and the ``imageio-ffmpeg`` wheel does not include it. Rather than make
duration measurement depend on a tool that may not exist, we fall back to
parsing ``ffmpeg -i``'s own report of the stream, which is always available
whenever ffmpeg itself is.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

from apps.api.core.config import settings

logger = logging.getLogger(__name__)


class MediaToolError(RuntimeError):
    """An ffmpeg invocation failed."""


class MediaToolMissing(MediaToolError):
    """ffmpeg could not be found at all."""


@lru_cache(maxsize=1)
def ffmpeg_path() -> str:
    """Absolute path to an ffmpeg binary, or raise."""
    if settings.FFMPEG_BINARY:
        if Path(settings.FFMPEG_BINARY).exists():
            return settings.FFMPEG_BINARY
        raise MediaToolMissing(
            f"FFMPEG_BINARY points at {settings.FFMPEG_BINARY}, which does not exist."
        )

    found = shutil.which("ffmpeg")
    if found:
        return found

    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        pass

    raise MediaToolMissing(
        "ffmpeg is not installed. Install it with your package manager "
        "(apt-get install ffmpeg), or `pip install imageio-ffmpeg` for a "
        "self-contained static build, or set FFMPEG_BINARY."
    )


@lru_cache(maxsize=1)
def ffprobe_path() -> str | None:
    """Absolute path to ffprobe, or None. Callers must tolerate None."""
    if settings.FFPROBE_BINARY:
        return settings.FFPROBE_BINARY if Path(settings.FFPROBE_BINARY).exists() else None
    return shutil.which("ffprobe")


def ffmpeg_unavailable_reason() -> str | None:
    """Why rendering cannot run, or None when it can.

    Same shape as the TTS availability probe so the pipeline can report
    every missing dependency in one pass instead of discovering them one
    crash at a time.
    """
    try:
        ffmpeg_path()
    except MediaToolMissing as exc:
        return str(exc)
    return None


def _reset_tool_cache() -> None:
    """Clear the resolved-path caches. For tests that patch settings."""
    ffmpeg_path.cache_clear()
    ffprobe_path.cache_clear()


def run_ffmpeg(args: list[str], timeout: int | None = None) -> subprocess.CompletedProcess:
    """Run ffmpeg with the given arguments.

    ``-nostdin`` matters: without it ffmpeg can consume the parent process's
    stdin and wedge a worker. ``-loglevel error`` keeps the captured stderr
    small enough to put in an error message.
    """
    binary = ffmpeg_path()
    cmd = [binary, "-nostdin", "-hide_banner", "-loglevel", "error", *args]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout or settings.RENDER_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise MediaToolError(
            f"ffmpeg timed out after {exc.timeout:.0f}s. The render is too long "
            f"or the source media is unreadable."
        ) from exc

    if result.returncode != 0:
        tail = (result.stderr or "").strip().splitlines()[-6:]
        raise MediaToolError("ffmpeg failed: " + " | ".join(tail))

    return result


_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d\d):(\d\d\.\d+)")


def probe_duration(path: str | Path) -> float:
    """Length of a media file in seconds.

    Prefers ffprobe; falls back to reading ffmpeg's own stream report, which
    means duration measurement never becomes the thing that breaks a render.
    """
    path = str(path)
    if not Path(path).exists():
        raise MediaToolError(f"Cannot measure {path}: the file does not exist.")

    probe = ffprobe_path()
    if probe:
        result = subprocess.run(
            [
                probe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        value = (result.stdout or "").strip()
        if result.returncode == 0 and value and value != "N/A":
            try:
                return float(value)
            except ValueError:
                pass

    # Fall back to ffmpeg's banner. Asking it to transcode to null means it
    # reads the file and reports what it found; exit status is ignored
    # because "no output specified" is an error even when the probe worked.
    result = subprocess.run(
        [ffmpeg_path(), "-nostdin", "-hide_banner", "-i", path],
        capture_output=True,
        text=True,
        timeout=60,
    )
    match = _DURATION_RE.search(result.stderr or "")
    if match:
        hours, minutes, seconds = match.groups()
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)

    raise MediaToolError(f"Could not determine the duration of {path}.")


def has_video_stream(path: str | Path) -> bool:
    """Whether a file carries a decodable video stream."""
    result = subprocess.run(
        [ffmpeg_path(), "-nostdin", "-hide_banner", "-i", str(path)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return "Video:" in (result.stderr or "")


#: Codecs that mean "one picture", even though ffmpeg calls them video.
STILL_IMAGE_CODECS = frozenset(
    {"mjpeg", "png", "webp", "bmp", "tiff", "jpeg2000", "ppm", "pgm"}
)

_CODEC_RE = re.compile(r"Stream #\d+:\d+.*?: Video: (\w+)")


def is_still_image(path: str | Path) -> bool:
    """Whether a file is a single picture rather than moving footage.

    Worth checking rather than trusting a provider's declared type: the two
    are built from completely different ffmpeg invocations (``-loop 1`` plus
    zoompan versus ``-stream_loop``), and feeding the wrong one a mismatched
    file fails with ``Option loop not found``, which says nothing useful
    about what actually went wrong.
    """
    result = subprocess.run(
        [ffmpeg_path(), "-nostdin", "-hide_banner", "-i", str(path)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    stderr = result.stderr or ""

    match = _CODEC_RE.search(stderr)
    if match and match.group(1).lower() in STILL_IMAGE_CODECS:
        return True

    # A file ffmpeg cannot assign a duration to is not playable footage.
    return "Duration: N/A" in stderr and "Video:" in stderr

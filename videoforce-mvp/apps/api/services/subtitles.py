"""Subtitle generation.

Timings come from the measured duration of each synthesised audio segment,
not from running speech recognition over our own narration. We already know
what the words are -- transcribing them back would add a heavy dependency,
take longer than the render itself, and introduce recognition errors into
text that was never uncertain.

Within a segment, time is split across caption chunks in proportion to their
character count. That is an approximation of speech rate, and a good one:
chunks come from the same sentence spoken by the same voice, so the
characters-per-second rate is near constant across them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: Captions longer than this are hard to read on a phone at arm's length.
MAX_CHARS_PER_CUE = 42
MAX_WORDS_PER_CUE = 8

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_WHITESPACE = re.compile(r"\s+")


@dataclass
class Cue:
    index: int
    start: float
    end: float
    text: str


def split_sentences(text: str) -> list[str]:
    """Break narration into sentences, discarding empties."""
    normalised = _WHITESPACE.sub(" ", (text or "").strip())
    if not normalised:
        return []
    parts = [p.strip() for p in _SENTENCE_SPLIT.split(normalised)]
    return [p for p in parts if p]


def chunk_caption(text: str) -> list[str]:
    """Split one sentence into screen-sized caption lines."""
    words = (text or "").split()
    if not words:
        return []

    chunks: list[str] = []
    current: list[str] = []

    for word in words:
        candidate = current + [word]
        too_long = len(" ".join(candidate)) > MAX_CHARS_PER_CUE
        too_many = len(candidate) > MAX_WORDS_PER_CUE
        if current and (too_long or too_many):
            chunks.append(" ".join(current))
            current = [word]
        else:
            current = candidate

    if current:
        chunks.append(" ".join(current))
    return chunks


def build_cues(segments: list[tuple[str, float, float]]) -> list[Cue]:
    """Turn ``(text, start, duration)`` segments into timed cues.

    Each segment is subdivided into caption chunks weighted by length.
    """
    cues: list[Cue] = []
    index = 1

    for text, start, duration in segments:
        chunks = chunk_caption(text)
        if not chunks or duration <= 0:
            continue

        total_chars = sum(len(c) for c in chunks) or 1
        cursor = start

        for position, chunk in enumerate(chunks):
            share = duration * (len(chunk) / total_chars)
            # Absorb rounding drift into the final chunk so a cue never
            # overruns its segment and collides with the next one.
            if position == len(chunks) - 1:
                end = start + duration
            else:
                end = cursor + share

            if end > cursor:
                cues.append(Cue(index=index, start=cursor, end=end, text=chunk))
                index += 1
            cursor = end

    return cues


def format_timestamp(seconds: float) -> str:
    """SRT timestamp: ``HH:MM:SS,mmm``."""
    if seconds < 0:
        seconds = 0.0
    milliseconds = int(round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    secs, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def to_srt(cues: list[Cue]) -> str:
    """Render cues as an SRT document."""
    blocks = []
    for cue in cues:
        blocks.append(
            f"{cue.index}\n"
            f"{format_timestamp(cue.start)} --> {format_timestamp(cue.end)}\n"
            f"{cue.text}\n"
        )
    return "\n".join(blocks)


def _ass_timestamp(seconds: float) -> str:
    """ASS timestamp: ``H:MM:SS.cc`` (centiseconds, single-digit hour)."""
    if seconds < 0:
        seconds = 0.0
    centis = int(round(seconds * 100))
    hours, centis = divmod(centis, 360_000)
    minutes, centis = divmod(centis, 6_000)
    secs, centis = divmod(centis, 100)
    return f"{hours:d}:{minutes:02d}:{secs:02d}.{centis:02d}"


def _ass_escape(text: str) -> str:
    """Escape caption text for an ASS dialogue line."""
    return (
        text.replace("\\", "\\\\")
        .replace("{", "\\{")
        .replace("}", "\\}")
        .replace("\n", "\\N")
    )


def to_ass(
    cues: list[Cue],
    width: int,
    height: int,
    font_size: int,
    font_name: str = "DejaVu Sans",
    margin_v: int | None = None,
) -> str:
    """Render cues as an ASS document sized to the actual video frame.

    This exists because burning an SRT in gives unusable results. libass
    lays subtitles out against the script's declared resolution, and an SRT
    declares none -- so ffmpeg falls back to a 384x288 canvas and then
    scales the result up to the real frame. On a 1080x1920 video that
    multiplies every size by nearly seven: a 28pt font renders at ~186px and
    a 160px bottom margin lands the text near the top of the screen.

    Declaring PlayResX/PlayResY to match the video makes every value here a
    real pixel measurement, which is both predictable and adjustable.
    """
    margin_v = margin_v if margin_v is not None else int(height * 0.12)
    margin_h = int(width * 0.08)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,{max(2, font_size // 12)},2,2,{margin_h},{margin_h},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    lines = [
        f"Dialogue: 0,{_ass_timestamp(cue.start)},{_ass_timestamp(cue.end)},"
        f"Default,,0,0,0,,{_ass_escape(cue.text)}"
        for cue in cues
    ]
    return header + "\n".join(lines) + "\n"


def watermark_ass(
    text: str,
    width: int,
    height: int,
    font_size: int | None = None,
    font_name: str = "DejaVu Sans",
) -> str:
    """A single always-on caption, used as a branding watermark.

    Drawn with libass rather than ffmpeg's ``drawtext`` because burning in
    captions already makes libass a hard requirement, while ``drawtext`` is
    an optional build flag -- the static ffmpeg wheel used on checkouts
    without a system build omits it entirely, and the watermark silently
    failed there. One text engine, one dependency.

    Placed top-right so it cannot collide with the captions along the
    bottom.
    """
    font_size = font_size or max(18, int(height * 0.022))
    margin = int(width * 0.03)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Mark,{font_name},{font_size},&H40FFFFFF,&H000000FF,&H80000000,&H00000000,-1,0,0,0,100,100,0,0,1,2,0,9,{margin},{margin},{margin},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,9:59:59.99,Mark,,0,0,0,,{_ass_escape(text)}
"""
    return header


def escape_for_filter(path: str) -> str:
    """Escape a path for use inside an ffmpeg filter argument.

    ffmpeg parses filter graphs before the filter sees its arguments, so
    colons, backslashes, commas and quotes in a path all need escaping or
    the graph fails to parse. On Linux this mostly matters for paths
    containing a colon, which temp directories occasionally produce.
    """
    return (
        path.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
        .replace(",", "\\,")
        .replace("[", "\\[")
        .replace("]", "\\]")
    )

"""Caption generation and timing."""

from __future__ import annotations

import re

from apps.api.services import subtitles as subs


# --- Splitting ----------------------------------------------------------------


def test_sentences_split_on_terminal_punctuation():
    assert subs.split_sentences("One. Two! Three?") == ["One.", "Two!", "Three?"]


def test_sentence_splitting_collapses_whitespace():
    assert subs.split_sentences("  A   sentence\n\nhere.  ") == ["A sentence here."]


def test_empty_script_yields_no_sentences():
    assert subs.split_sentences("") == []
    assert subs.split_sentences("   \n  ") == []


def test_captions_are_chunked_for_readability():
    long_line = "Ocean plastic is choking marine ecosystems all around the world today"
    chunks = subs.chunk_caption(long_line)

    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= subs.MAX_CHARS_PER_CUE
        assert len(chunk.split()) <= subs.MAX_WORDS_PER_CUE
    # No words may be lost or duplicated by chunking.
    assert " ".join(chunks) == long_line


def test_a_single_overlong_word_still_produces_a_chunk():
    chunks = subs.chunk_caption("Pneumonoultramicroscopicsilicovolcanoconiosis")
    assert len(chunks) == 1


# --- Timing -------------------------------------------------------------------


def test_cues_stay_inside_their_segment():
    """A segment's last cue ends exactly when the segment does."""
    text = "Ocean plastic is choking marine ecosystems all around the world today"
    cues = subs.build_cues([(text, 10.0, 4.0)])

    assert cues[0].start == 10.0
    assert cues[-1].end == 14.0


def test_cues_do_not_overlap_or_leave_gaps():
    cues = subs.build_cues(
        [
            ("Ocean plastic is choking marine ecosystems worldwide.", 0.0, 4.0),
            ("Every single year eleven million tonnes enter the sea.", 4.0, 5.0),
        ]
    )

    for earlier, later in zip(cues, cues[1:]):
        assert earlier.end <= later.start + 1e-6
        assert later.start >= earlier.start

    assert cues[0].start == 0.0
    assert cues[-1].end == 9.0


def test_cue_time_is_shared_in_proportion_to_length():
    """A longer chunk is on screen longer, because it takes longer to say."""
    cues = subs.build_cues([("Short bit. " + "a" * 60, 0.0, 10.0)])
    durations = [c.end - c.start for c in cues]
    lengths = [len(c.text) for c in cues]

    longest = lengths.index(max(lengths))
    assert durations[longest] == max(durations)


def test_zero_duration_segments_are_dropped():
    assert subs.build_cues([("Something", 0.0, 0.0)]) == []


def test_cue_indices_are_sequential():
    cues = subs.build_cues([("One two three four five six seven eight nine.", 0.0, 5.0)])
    assert [c.index for c in cues] == list(range(1, len(cues) + 1))


# --- SRT ----------------------------------------------------------------------


def test_srt_timestamp_format():
    assert subs.format_timestamp(0) == "00:00:00,000"
    assert subs.format_timestamp(3661.5) == "01:01:01,500"
    assert subs.format_timestamp(-5) == "00:00:00,000"


def test_srt_structure_is_valid():
    cues = subs.build_cues([("Hello there world.", 0.0, 2.0)])
    srt = subs.to_srt(cues)

    assert re.match(r"^1\n00:00:00,000 --> 00:00:02,000\n", srt)
    assert srt.endswith("\n")


# --- ASS ----------------------------------------------------------------------


def test_ass_declares_the_video_resolution():
    """Without PlayRes matching the frame, libass scales from 384x288 and the
    captions land in the wrong place at the wrong size."""
    cues = subs.build_cues([("Hello there.", 0.0, 2.0)])
    ass = subs.to_ass(cues, width=1080, height=1920, font_size=56)

    assert "PlayResX: 1080" in ass
    assert "PlayResY: 1920" in ass
    assert "DejaVu Sans,56," in ass


def test_ass_timestamps_use_centiseconds():
    cues = [subs.Cue(index=1, start=61.25, end=62.5, text="x")]
    ass = subs.to_ass(cues, width=1080, height=1920, font_size=56)

    assert "0:01:01.25,0:01:02.50" in ass


def test_ass_bottom_margin_scales_with_the_frame():
    cues = [subs.Cue(index=1, start=0, end=1, text="x")]
    tall = subs.to_ass(cues, width=1080, height=1920, font_size=56)

    # Alignment 2 is bottom-centre; the margin is a real pixel count.
    style = [line for line in tall.splitlines() if line.startswith("Style:")][0]
    fields = style.split(",")
    assert fields[18] == "2"
    assert int(fields[21]) == int(1920 * 0.12)


def test_ass_escapes_braces_that_would_be_read_as_overrides():
    cues = [subs.Cue(index=1, start=0, end=1, text="Use {braces} here")]
    ass = subs.to_ass(cues, width=1080, height=1920, font_size=56)

    assert "\\{braces\\}" in ass


# --- Filter escaping ----------------------------------------------------------


def test_filter_escaping_protects_the_graph_separators():
    escaped = subs.escape_for_filter("/tmp/a:b/c,d/captions.ass")
    assert "\\:" in escaped
    assert "\\," in escaped


# --- Watermark ----------------------------------------------------------------


def test_watermark_is_a_single_always_on_cue():
    ass = subs.watermark_ass("HydraClip", width=1080, height=1920)

    dialogues = [l for l in ass.splitlines() if l.startswith("Dialogue:")]
    assert len(dialogues) == 1
    assert "HydraClip" in dialogues[0]
    assert "0:00:00.00" in dialogues[0]


def test_watermark_sits_top_right_away_from_the_captions():
    """Captions are bottom-centre (alignment 2); the mark must not collide."""
    ass = subs.watermark_ass("HydraClip", width=1080, height=1920)
    style = [l for l in ass.splitlines() if l.startswith("Style:")][0]

    # Alignment 9 is top-right in ASS numbering.
    assert style.split(",")[18] == "9"
    assert "PlayResY: 1920" in ass

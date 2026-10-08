"""`_wrap_paragraph()` - the word-wrapping helper added after a real
observed bug where `ParagraphElement.line_width` was defined in the schema
but silently ignored by the renderer, so any paragraph longer than a few
words rendered as one unbroken line running off both edges of the frame.
Pure function, no Manim/rendering involved - stays fast.
"""
from __future__ import annotations

from animation_engine.components.text import _wrap_paragraph


def test_short_content_is_a_single_line():
    result = _wrap_paragraph("Short text.", line_width=9.0, font_size=26)
    assert "\n" not in result
    assert result == "Short text."


def test_long_content_wraps_into_multiple_lines():
    content = (
        "Two pointers efficiently finds a pair sum in a sorted array by "
        "eliminating many invalid pairs with each move."
    )
    result = _wrap_paragraph(content, line_width=9.0, font_size=26)
    lines = result.split("\n")
    assert len(lines) > 1
    # Every line should respect the estimated character budget for this
    # line_width/font_size combination - no single line should still be
    # anywhere near the full original content length.
    assert all(len(line) < len(content) for line in lines)
    # No words dropped or duplicated.
    assert " ".join(lines).split() == content.split()


def test_wrapping_never_drops_a_single_oversized_word():
    result = _wrap_paragraph("supercalifragilisticexpialidocious", line_width=1.0, font_size=26)
    assert result == "supercalifragilisticexpialidocious"


def test_narrower_line_width_produces_more_lines():
    content = "one two three four five six seven eight nine ten eleven twelve"
    narrow = _wrap_paragraph(content, line_width=3.0, font_size=26)
    wide = _wrap_paragraph(content, line_width=15.0, font_size=26)
    assert len(narrow.split("\n")) > len(wide.split("\n"))

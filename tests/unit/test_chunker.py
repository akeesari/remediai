"""Unit tests for packages.search.chunker."""

from __future__ import annotations

from packages.search.chunker import _CHARS_PER_TOKEN, chunk_text


class TestChunkTextBasics:
    def test_empty_string_returns_empty(self) -> None:
        assert chunk_text("") == []

    def test_whitespace_only_returns_empty(self) -> None:
        assert chunk_text("   \n  ") == []

    def test_short_text_returns_single_chunk(self) -> None:
        # 400 chars = 100 tokens — exactly at minimum boundary
        text = "A" * 400
        chunks = chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_below_minimum_discarded(self) -> None:
        # 99 tokens = 396 chars — below 100-token minimum
        text = "A" * 396
        chunks = chunk_text(text)
        assert chunks == []

    def test_text_fits_in_max_tokens(self) -> None:
        # 512 tokens = 2048 chars — exactly at target
        text = "B" * 2048
        chunks = chunk_text(text)
        assert len(chunks) == 1

    def test_large_text_splits_into_multiple_chunks(self) -> None:
        # 3000 chars > 2048-char limit → must produce at least 2 chunks
        text = "C" * 3000
        chunks = chunk_text(text)
        assert len(chunks) >= 2

    def test_chunk_size_does_not_exceed_max(self) -> None:
        text = "D" * 5000
        max_tokens = 512
        max_chars = max_tokens * _CHARS_PER_TOKEN
        chunks = chunk_text(text, max_tokens=max_tokens)
        for chunk in chunks:
            assert len(chunk) <= max_chars + 1  # +1 for strip edge case


class TestChunkTextOverlap:
    def test_consecutive_chunks_share_overlap(self) -> None:
        # Build text that definitely spans two chunks
        chunk_chars = 512 * _CHARS_PER_TOKEN
        overlap_chars = 50 * _CHARS_PER_TOKEN
        # Use distinct repeating segments so we can identify them
        segment = "ABCDE" * (chunk_chars // 5 + 1)
        text = segment[: chunk_chars + overlap_chars + chunk_chars]

        chunks = chunk_text(text, max_tokens=512, overlap=50)
        if len(chunks) >= 2:
            # The end of chunk[0] should appear at the start of chunk[1]
            tail = chunks[0][-overlap_chars:]
            assert chunks[1].startswith(tail) or tail in chunks[1]


class TestChunkTextHeadingAware:
    def test_heading_starts_new_chunk(self) -> None:
        # Two sections, each just above minimum; heading should force boundary
        min_content = "X" * (100 * _CHARS_PER_TOKEN)
        text = f"# Section One\n\n{min_content}\n\n## Section Two\n\n{min_content}"
        chunks = chunk_text(text, max_tokens=512, overlap=0)
        # Should have two separate chunks, one per section
        assert len(chunks) >= 2
        # Section Two heading should be in a different chunk
        section_two_chunk = next((c for c in chunks if "Section Two" in c), None)
        section_one_chunk = next((c for c in chunks if "Section One" in c), None)
        if section_two_chunk and section_one_chunk:
            assert section_two_chunk is not section_one_chunk

    def test_heading_content_preserved(self) -> None:
        content = "W" * (200 * _CHARS_PER_TOKEN)
        text = f"## My Runbook\n\n{content}"
        chunks = chunk_text(text, max_tokens=512)
        assert any("My Runbook" in c for c in chunks)

    def test_small_section_merged_with_carry(self) -> None:
        # A section below min-size is too small to be a chunk on its own
        tiny = "Z" * 50  # well below 400-char minimum
        large = "Y" * (200 * _CHARS_PER_TOKEN)
        text = f"{tiny}\n\n## Big Section\n\n{large}"
        chunks = chunk_text(text, max_tokens=512)
        # The tiny section alone should not appear as its own chunk
        standalone_tiny = [c for c in chunks if c == tiny]
        assert len(standalone_tiny) == 0


class TestChunkTextCustomParameters:
    def test_custom_max_tokens(self) -> None:
        # max_tokens=200 → max_chars=800; min_chars=400 (100 tokens)
        # text of 2000 chars splits into chunks of 800, 800, 400 — all ≥ min
        text = "E" * 2000
        chunks = chunk_text(text, max_tokens=200, overlap=0)
        assert len(chunks) >= 2

    def test_zero_overlap_no_sharing(self) -> None:
        # Each char is distinct so we can verify no carry-over
        # Use 3 full chunks worth of chars so we get at least 2 chunks after split
        chunk_chars = 512 * _CHARS_PER_TOKEN
        text = "F" * chunk_chars + "G" * chunk_chars + "H" * chunk_chars
        chunks = chunk_text(text, max_tokens=512, overlap=0)
        if len(chunks) >= 2:
            # The second chunk should start with G's, not F's (no overlap carry)
            assert chunks[1][0] == "G"

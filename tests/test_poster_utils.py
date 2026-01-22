"""Tests for the poster utilities module."""

import tempfile
from pathlib import Path

import pytest

from onepace_assistant.poster_utils import (
    copy_poster_to_arc_dir,
    find_poster_for_arc,
    normalize_slug_for_matching,
)


class TestNormalizeSlugForMatching:
    """Tests for slug normalization to regex pattern."""

    def test_simple_slug(self):
        pattern = normalize_slug_for_matching("romance-dawn")
        assert "romance" in pattern
        assert "dawn" in pattern

    def test_multi_word_slug(self):
        pattern = normalize_slug_for_matching("water-seven")
        assert "water" in pattern
        assert "seven" in pattern


class TestFindPosterForArc:
    """Tests for poster discovery by arc slug."""

    def test_find_poster_exact_match(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            posters_dir = Path(tmpdir)
            poster_file = posters_dir / "romance-dawn.jpg"
            poster_file.write_bytes(b"fake image data")

            result = find_poster_for_arc("romance-dawn", posters_dir)
            assert result == poster_file

    def test_find_poster_with_spaces(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            posters_dir = Path(tmpdir)
            poster_file = posters_dir / "Romance Dawn.png"
            poster_file.write_bytes(b"fake image data")

            result = find_poster_for_arc("romance-dawn", posters_dir)
            assert result == poster_file

    def test_find_poster_with_underscores(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            posters_dir = Path(tmpdir)
            poster_file = posters_dir / "romance_dawn.jpg"
            poster_file.write_bytes(b"fake image data")

            result = find_poster_for_arc("romance-dawn", posters_dir)
            assert result == poster_file

    def test_find_poster_mixed_case(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            posters_dir = Path(tmpdir)
            poster_file = posters_dir / "ROMANCE-DAWN.jpg"
            poster_file.write_bytes(b"fake image data")

            result = find_poster_for_arc("romance-dawn", posters_dir)
            assert result == poster_file

    def test_find_poster_multiple_extensions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            posters_dir = Path(tmpdir)
            
            # Test each supported extension
            for ext in (".jpg", ".jpeg", ".png", ".webp"):
                poster_file = posters_dir / f"test-arc{ext}"
                poster_file.write_bytes(b"fake image data")
                
                result = find_poster_for_arc("test-arc", posters_dir)
                assert result is not None
                assert result.suffix == ext
                
                # Clean up for next iteration
                poster_file.unlink()

    def test_find_poster_with_extra_text(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            posters_dir = Path(tmpdir)
            poster_file = posters_dir / "romance-dawn-poster-v2.jpg"
            poster_file.write_bytes(b"fake image data")

            result = find_poster_for_arc("romance-dawn", posters_dir)
            assert result == poster_file

    def test_find_poster_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            posters_dir = Path(tmpdir)
            # Create a different arc's poster
            other_poster = posters_dir / "water-seven.jpg"
            other_poster.write_bytes(b"fake image data")

            result = find_poster_for_arc("romance-dawn", posters_dir)
            assert result is None

    def test_find_poster_multiple_matches_returns_first(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            posters_dir = Path(tmpdir)
            # Create multiple matching files
            poster1 = posters_dir / "romance-dawn.jpg"
            poster2 = posters_dir / "romance-dawn-alt.png"
            poster1.write_bytes(b"first")
            poster2.write_bytes(b"second")

            result = find_poster_for_arc("romance-dawn", posters_dir)
            assert result is not None
            # Should find one of them (order may vary by OS)
            assert "romance-dawn" in result.stem.lower().replace("_", "-").replace(" ", "-")

    def test_find_poster_nonexistent_directory(self):
        result = find_poster_for_arc("romance-dawn", Path("/nonexistent/path"))
        assert result is None

    def test_find_poster_ignores_unsupported_extensions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            posters_dir = Path(tmpdir)
            # Create file with unsupported extension
            bad_file = posters_dir / "romance-dawn.gif"
            bad_file.write_bytes(b"fake image data")

            result = find_poster_for_arc("romance-dawn", posters_dir)
            assert result is None

    def test_find_poster_ignores_directories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            posters_dir = Path(tmpdir)
            # Create a directory with matching name
            sub_dir = posters_dir / "romance-dawn.jpg"
            sub_dir.mkdir()

            result = find_poster_for_arc("romance-dawn", posters_dir)
            assert result is None


class TestCopyPosterToArcDir:
    """Tests for poster copying functionality."""

    def test_copy_poster_to_arc_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            source = tmppath / "source.jpg"
            arc_dir = tmppath / "romance-dawn"
            arc_dir.mkdir()
            
            source.write_bytes(b"test image content")
            
            result = copy_poster_to_arc_dir(source, arc_dir)
            
            assert result.exists()
            assert result.name == "poster.jpg"
            assert result.read_bytes() == b"test image content"

    def test_copy_poster_creates_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            source = tmppath / "source.jpg"
            arc_dir = tmppath / "new-arc" / "nested"
            
            source.write_bytes(b"test image content")
            
            result = copy_poster_to_arc_dir(source, arc_dir)
            
            assert arc_dir.exists()
            assert result.exists()
            assert result.name == "poster.jpg"

    def test_copy_poster_preserves_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            source = tmppath / "source.jpg"
            arc_dir = tmppath / "romance-dawn"
            arc_dir.mkdir()
            
            # Create file with specific content
            original_content = b"\x89PNG\r\n\x1a\n" + b"x" * 1000
            source.write_bytes(original_content)
            
            result = copy_poster_to_arc_dir(source, arc_dir)
            
            assert result.read_bytes() == original_content

    def test_copy_poster_overwrites_existing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            source = tmppath / "source.jpg"
            arc_dir = tmppath / "romance-dawn"
            arc_dir.mkdir()
            
            # Create existing poster
            existing = arc_dir / "poster.jpg"
            existing.write_bytes(b"old content")
            
            source.write_bytes(b"new content")
            
            result = copy_poster_to_arc_dir(source, arc_dir)
            
            assert result.read_bytes() == b"new content"

    def test_copy_poster_custom_target_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            source = tmppath / "source.png"
            arc_dir = tmppath / "romance-dawn"
            arc_dir.mkdir()
            
            source.write_bytes(b"test image content")
            
            result = copy_poster_to_arc_dir(source, arc_dir, target_name="cover.jpg")
            
            assert result.name == "cover.jpg"
            assert result.exists()

    def test_copy_poster_source_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            source = tmppath / "nonexistent.jpg"
            arc_dir = tmppath / "romance-dawn"
            
            with pytest.raises(FileNotFoundError):
                copy_poster_to_arc_dir(source, arc_dir)

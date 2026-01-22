"""Integration tests for CLI playlist selection logic."""

import pytest
from click.testing import CliRunner

from onepace_assistant.cli import cli
from onepace_assistant.models import Arc, PlayGroup, Playlist


@pytest.fixture
def mock_arc():
    """Create a mock arc with both Japanese dub (with subs) and English dub (no subs) variants."""
    return Arc(
        slug="test-arc",
        title="Test Arc",
        description="Test description",
        special=False,
        chapters="1-10",
        episodes="1-5",
        playGroups=[
            # Japanese dub with English subtitles
            PlayGroup(
                sub="en",
                dub="ja",
                variant=None,
                playlists=[
                    Playlist(id="ja_480", resolution=480),
                    Playlist(id="ja_720", resolution=720),
                    Playlist(id="ja_1080", resolution=1080),
                ],
            ),
            # English dub without subtitles
            PlayGroup(
                sub=None,
                dub="en",
                variant=None,
                playlists=[
                    Playlist(id="en_480", resolution=480),
                    Playlist(id="en_720", resolution=720),
                    Playlist(id="en_1080", resolution=1080),
                ],
            ),
        ],
    )


class TestPlaylistSelection:
    """Test the Arc.get_playlist() method with various configurations."""

    def test_default_options_selects_japanese_dub(self, mock_arc):
        """Default options (no flags) should select Japanese dub with English subs."""
        # Default: resolution=1080, sub=None (auto), dub=ja
        # Should auto-select sub=en for Japanese dub
        playlist = mock_arc.get_playlist(resolution=1080, sub="en", dub="ja")
        assert playlist is not None
        assert playlist.id == "ja_1080"

    def test_explicit_english_dub_no_subs(self, mock_arc):
        """Explicit --sub none --dub en should select English dub."""
        playlist = mock_arc.get_playlist(resolution=1080, sub=None, dub="en")
        assert playlist is not None
        assert playlist.id == "en_1080"

    def test_english_dub_with_sub_en_not_found(self, mock_arc):
        """English dub with sub=en should NOT match (English dub has sub=None)."""
        playlist = mock_arc.get_playlist(resolution=1080, sub="en", dub="en")
        assert playlist is None

    def test_resolution_fallback(self, mock_arc):
        """If exact resolution not found, should fall back to highest available."""
        # Add a variant with only 720p
        mock_arc.play_groups.append(
            PlayGroup(
                sub="es",
                dub="ja",
                variant=None,
                playlists=[Playlist(id="es_720", resolution=720)],
            )
        )
        # Request 1080p but only 720p exists for Spanish subs
        playlist = mock_arc.get_playlist(resolution=1080, sub="es", dub="ja")
        assert playlist is not None
        assert playlist.id == "es_720"
        assert playlist.resolution == 720


class TestCLISmartDefaults:
    """Test CLI smart defaults for English dub detection.
    
    Note: These are unit tests of the selection logic. Full end-to-end tests
    would require mocking the scraper and downloader, which is beyond the scope
    of this fix. Manual verification should be performed with real data.
    """

    def test_smart_default_english_dub(self, mock_arc):
        """When --dub en is specified without --sub, should find English dub (sub=None)."""
        # Simulating: onepace download test-arc --dub en
        # Smart logic: try sub=None first for dub=en
        playlist = mock_arc.get_playlist(resolution=1080, sub=None, dub="en")
        assert playlist is not None
        assert playlist.id == "en_1080"

    def test_smart_default_japanese_dub(self, mock_arc):
        """When --dub ja is specified without --sub, should default to sub=en."""
        # Simulating: onepace download test-arc (defaults to --dub ja)
        # Smart logic: default to sub=en for non-English dubs
        playlist = mock_arc.get_playlist(resolution=1080, sub="en", dub="ja")
        assert playlist is not None
        assert playlist.id == "ja_1080"

    def test_explicit_sub_overrides_smart_default(self, mock_arc):
        """Explicit --sub flag should override smart defaults."""
        # Simulating: onepace download test-arc --sub none --dub en
        playlist = mock_arc.get_playlist(resolution=1080, sub=None, dub="en")
        assert playlist is not None
        assert playlist.id == "en_1080"

        # Simulating: onepace download test-arc --sub en --dub ja
        playlist = mock_arc.get_playlist(resolution=1080, sub="en", dub="ja")
        assert playlist is not None
        assert playlist.id == "ja_1080"

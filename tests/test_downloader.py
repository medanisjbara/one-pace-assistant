"""Tests for download functionality."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from onepace_assistant.downloader import (
    DownloadError,
    PixelDrainFile,
    PixelDrainList,
    Playlist,
    download_playlist_zip_sync,
    validate_api_key_sync,
)


class TestZipDownload:
    """Test zip download functionality."""

    def test_download_href_captured_in_model(self):
        """Test that download_href is properly captured in PixelDrainList model."""
        file_list = PixelDrainList(
            id="test123",
            title="Test List",
            download_href="/list/test123/zip",
            files=[
                PixelDrainFile(id="file1", name="episode1.mkv", size=1024),
                PixelDrainFile(id="file2", name="episode2.mkv", size=2048),
            ],
        )
        
        assert file_list.download_href == "/list/test123/zip"
        assert len(file_list.files) == 2

    def test_download_href_optional(self):
        """Test that download_href is optional (backwards compatibility)."""
        file_list = PixelDrainList(
            id="test123",
            title="Test List",
            files=[
                PixelDrainFile(id="file1", name="episode1.mkv", size=1024),
            ],
        )
        
        assert file_list.download_href is None
        assert len(file_list.files) == 1

    @patch("onepace_assistant.downloader.fetch_playlist_files_sync")
    def test_skips_download_when_all_files_exist(self, mock_fetch):
        """Test that zip download skips when all files already exist."""
        mock_fetch.return_value = PixelDrainList(
            id="test123",
            title="Test List",
            download_href="/list/test123/zip",
            files=[
                PixelDrainFile(id="file1", name="episode1.mkv", size=10),
                PixelDrainFile(id="file2", name="episode2.mkv", size=20),
            ],
        )
        
        playlist = Playlist(id="test123", resolution=1080)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            
            # Create existing files with correct sizes
            (output_dir / "episode1.mkv").write_bytes(b"0" * 10)
            (output_dir / "episode2.mkv").write_bytes(b"0" * 20)
            
            # Should skip download and return existing paths
            result = download_playlist_zip_sync(playlist, output_dir, resume=True)
            
            assert len(result) == 2
            assert all(p.exists() for p in result)


class TestValidateApiKey:
    """Tests for validate_api_key_sync."""

    @patch("onepace_assistant.downloader.httpx.Client")
    def test_valid_key_does_not_raise(self, mock_client_cls):
        mock_response = mock_client_cls.return_value.__enter__.return_value.get.return_value
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None

        validate_api_key_sync("valid-key")  # should not raise

    @patch("onepace_assistant.downloader.httpx.Client")
    def test_invalid_key_raises_download_error(self, mock_client_cls):
        mock_response = mock_client_cls.return_value.__enter__.return_value.get.return_value
        mock_response.status_code = 401

        with pytest.raises(DownloadError, match="Invalid PixelDrain API key"):
            validate_api_key_sync("bad-key")

    @patch("onepace_assistant.downloader.httpx.Client")
    def test_key_sent_as_basic_auth(self, mock_client_cls):
        mock_get = mock_client_cls.return_value.__enter__.return_value.get
        mock_get.return_value.status_code = 200
        mock_get.return_value.raise_for_status.return_value = None

        validate_api_key_sync("my-api-key")

        _, kwargs = mock_get.call_args
        assert kwargs["auth"] == ("", "my-api-key")

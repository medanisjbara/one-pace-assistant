"""Tests for the scraper module."""

import pytest

from onepace_assistant.scraper import extract_rsc_payload, _unescape_rsc_string, _normalize_undefined


class TestUnescapeRscString:
    """Tests for RSC string unescaping."""

    def test_unescape_quotes(self):
        assert _unescape_rsc_string('\\"test\\"') == '"test"'

    def test_unescape_newlines(self):
        assert _unescape_rsc_string("line1\\nline2") == "line1\nline2"

    def test_unescape_backslashes(self):
        assert _unescape_rsc_string("path\\\\to\\\\file") == "path\\to\\file"


class TestNormalizeUndefined:
    """Tests for $undefined normalization."""

    def test_normalize_dict_with_undefined(self):
        data = {"sub": "$undefined", "dub": "en", "variant": "$undefined"}
        result = _normalize_undefined(data)
        assert result == {"sub": None, "dub": "en", "variant": None}

    def test_normalize_list_with_undefined(self):
        data = ["$undefined", "en", "ja", "$undefined"]
        result = _normalize_undefined(data)
        assert result == [None, "en", "ja", None]

    def test_normalize_nested_structures(self):
        data = {
            "playGroups": [
                {"sub": "$undefined", "dub": "en", "playlists": []},
                {"sub": "en", "dub": "ja", "variant": "$undefined"},
            ]
        }
        result = _normalize_undefined(data)
        assert result == {
            "playGroups": [
                {"sub": None, "dub": "en", "playlists": []},
                {"sub": "en", "dub": "ja", "variant": None},
            ]
        }

    def test_normalize_preserves_other_values(self):
        data = {
            "title": "Romance Dawn",
            "description": "Test with $undefined in text",
            "sub": "$undefined",
        }
        result = _normalize_undefined(data)
        # Only exact match "$undefined" should be converted
        assert result == {
            "title": "Romance Dawn",
            "description": "Test with $undefined in text",
            "sub": None,
        }


class TestExtractRscPayload:
    """Tests for RSC payload extraction."""

    def test_extract_single_payload(self):
        html = '''
        <html>
        <script>self.__next_f.push([1,"test payload data"])</script>
        </html>
        '''
        payload = extract_rsc_payload(html)
        assert "test payload data" in payload

    def test_extract_multiple_payloads(self):
        html = '''
        <html>
        <script>self.__next_f.push([1,"chunk1"])</script>
        <script>self.__next_f.push([1,"chunk2"])</script>
        </html>
        '''
        payload = extract_rsc_payload(html)
        assert "chunk1" in payload
        assert "chunk2" in payload

    def test_no_payload_raises_error(self):
        from onepace_assistant.scraper import ScraperError

        html = "<html><body>No RSC here</body></html>"
        with pytest.raises(ScraperError):
            extract_rsc_payload(html)

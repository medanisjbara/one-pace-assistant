"""Scraper for One Pace metadata from onepace.net."""

import json
import re
from typing import Any

import httpx

from .models import Arc

ONEPACE_WATCH_URL = "https://onepace.net/en/watch"

# Regex to extract RSC payload data from Next.js script tags
RSC_PAYLOAD_PATTERN = re.compile(r'self\.__next_f\.push\(\[1,"(.+?)"\]\)', re.DOTALL)


class ScraperError(Exception):
    """Error during metadata scraping."""


def _unescape_rsc_string(s: str) -> str:
    """Unescape the RSC payload string."""
    # RSC payloads have escaped quotes and special chars
    return (
        s.replace('\\"', '"')
        .replace("\\n", "\n")
        .replace("\\\\", "\\")
    )


def _extract_arcs_array(payload: str) -> list[dict]:
    """Extract the arcs data array from the RSC payload."""
    # Find the data property containing the arcs array
    # Pattern: "data":[{"slug":... - we match the start then use bracket counting
    data_match = re.search(r'"data":\s*(\[{"slug":")', payload, re.DOTALL)
    if data_match:
        # Extract the array using bracket matching
        start_idx = data_match.start(1)
        arr_str = payload[start_idx:]
        
        bracket_count = 0
        end_idx = 0
        for i, c in enumerate(arr_str):
            if c == '[':
                bracket_count += 1
            elif c == ']':
                bracket_count -= 1
                if bracket_count == 0:
                    end_idx = i + 1
                    break
        
        if end_idx > 0:
            try:
                return json.loads(arr_str[:end_idx])
            except json.JSONDecodeError:
                pass

    raise ScraperError("Could not extract arcs data from RSC payload")


def _normalize_undefined(data: dict | list | Any) -> dict | list | Any:
    """Recursively replace '$undefined' strings with None.
    
    onepace.net's RSC payload contains the literal string '$undefined' for
    fields that should be null/None. This function normalizes those values.
    """
    if isinstance(data, dict):
        return {k: _normalize_undefined(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_normalize_undefined(item) for item in data]
    elif data == "$undefined":
        return None
    return data


def extract_rsc_payload(html: str) -> str:
    """Extract and combine RSC payload strings from HTML."""
    matches = RSC_PAYLOAD_PATTERN.findall(html)
    if not matches:
        raise ScraperError("No RSC payload found in HTML")

    # Combine all payload chunks
    combined = ""
    for match in matches:
        combined += _unescape_rsc_string(match)

    return combined


def parse_arcs_from_html(html: str) -> list[Arc]:
    """Parse arc metadata from HTML content."""
    payload = extract_rsc_payload(html)
    arcs_data = _extract_arcs_array(payload)

    arcs = []
    for arc_data in arcs_data:
        try:
            # Normalize $undefined strings to None before validation
            normalized_data = _normalize_undefined(arc_data)
            arc = Arc.model_validate(normalized_data)
            arcs.append(arc)
        except Exception as e:
            # Log but don't fail on individual arc parsing errors
            print(f"Warning: Failed to parse arc '{arc_data.get('slug', 'unknown')}': {e}")

    return arcs


async def fetch_metadata() -> list[Arc]:
    """Fetch and parse all arc metadata from onepace.net."""
    async with httpx.AsyncClient(
        headers={
            "User-Agent": "OnePaceAssistant/0.1.0 (https://github.com/one-pace-assistant)",
        },
        timeout=30.0,
    ) as client:
        response = await client.get(ONEPACE_WATCH_URL)
        response.raise_for_status()

    return parse_arcs_from_html(response.text)


def fetch_metadata_sync() -> list[Arc]:
    """Synchronous version of fetch_metadata for CLI use."""
    with httpx.Client(
        headers={
            "User-Agent": "OnePaceAssistant/0.1.0 (https://github.com/one-pace-assistant)",
        },
        timeout=30.0,
    ) as client:
        response = client.get(ONEPACE_WATCH_URL)
        response.raise_for_status()

    return parse_arcs_from_html(response.text)

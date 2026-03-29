"""Tests for the NFO generation module."""

import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from onepace_assistant.models import Arc
from onepace_assistant.nfo import generate_episode_nfo, generate_tvshow_nfo, _get_season_number


class TestGenerateTvshowNfo:
    """Tests for tvshow.nfo generation."""

    def test_generates_valid_xml(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir)
            nfo_path = generate_tvshow_nfo(output_path)

            assert nfo_path.exists()
            assert nfo_path.name == "tvshow.nfo"

            # Parse and validate XML
            tree = ET.parse(nfo_path)
            root = tree.getroot()
            assert root.tag == "tvshow"

    def test_contains_required_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir)
            nfo_path = generate_tvshow_nfo(output_path)

            tree = ET.parse(nfo_path)
            root = tree.getroot()

            assert root.find("title").text == "One Pace"
            assert root.find("plot") is not None
            assert "One Pace" in root.find("plot").text


class TestGenerateEpisodeNfo:
    """Tests for episode NFO generation."""

    @pytest.fixture
    def sample_arc(self):
        return Arc(
            slug="romance-dawn",
            title="Romance Dawn",
            description="Luffy sets out on an adventure",
            special=False,
            chapters="1-7",
            episodes="1-3",
            playGroups=[],
        )

    def test_generates_valid_xml(self, sample_arc):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            nfo_path = generate_episode_nfo(
                arc=sample_arc,
                episode_number=1,
                video_filename="Romance Dawn 01.mkv",
                output_dir=output_dir,
            )

            assert nfo_path.exists()
            assert nfo_path.name == "Romance Dawn 01.nfo"

            tree = ET.parse(nfo_path)
            root = tree.getroot()
            assert root.tag == "episodedetails"

    def test_contains_episode_info(self, sample_arc):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            nfo_path = generate_episode_nfo(
                arc=sample_arc,
                episode_number=3,
                video_filename="Romance Dawn 03.mkv",
                output_dir=output_dir,
                season_number=1,
            )

            tree = ET.parse(nfo_path)
            root = tree.getroot()

            assert root.find("title").text == "Romance Dawn 03"
            assert root.find("season").text == "1"
            assert root.find("episode").text == "3"
            assert root.find("showtitle").text == "One Pace"

    def test_get_season_number_from_arcs(self, sample_arc):
        # Since we're already testing with Romance Dawn we add a made up
        # arc so we don't get the default return of 1 and get 2 instead
        arcs = [
            Arc(slug="made-up",
                title="Made up so we don't get 1",
                special=False,
                chapters="0",
                episodes="0",
                playGroups=[],
                ),
            sample_arc,
            Arc(slug="orange-town",
                title="Orange Town",
                special=False,
                chapters="8-21",
                episodes="4-8",
                playGroups=[],
                ),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            nfo_path = generate_episode_nfo(
                arc=sample_arc,
                episode_number=3,
                video_filename="Romance Dawn 03.mkv",
                output_dir=output_dir,
                arcs=arcs,
            )

            tree = ET.parse(nfo_path)
            root = tree.getroot()
            assert root.find("season").text == "2"
        
        def test_season_number_falls_back_to_one(self, sample_arc):
            with tempfile.TemporaryDirectory() as tmpdir:
                output_dir = Path(tmpdir)
                nfo_path = generate_episode_nfo(
                    arc=sample_arc,
                    episode_number=3,
                    video_filename="Romance Dawn 03.mkv",
                    output_dir=output_dir,
                )

                tree = ET.parse(nfo_path)
                root = tree.getroot()
                assert root.find("season").text == "1"
        
        def test_explicit_season_number_overrides_arcs(self, sample_arc):
            arcs = [sample_arc]
            with tempfile.TemporaryDirectory() as tmpdir:
                output_dir = Path(tmpdir)
                nfo_path = generate_episode_nfo(
                    arc=sample_arc,
                    episode_number=3,
                    video_filename="Romance Dawn 03.mkv",
                    output_dir=output_dir,
                    season_number=5,
                    arcs=arcs
                )

            tree = ET.parse(nfo_path)
            root = tree.getroot()
            assert root.find("season").text == "5"

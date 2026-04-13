"""NFO file generation for media servers."""

from pathlib import Path
from xml.etree import ElementTree as ET
from xml.dom import minidom

from .models import Arc


def _prettify_xml(elem: ET.Element) -> str:
    """Return a pretty-printed XML string."""
    rough_string = ET.tostring(elem, encoding="unicode")
    reparsed = minidom.parseString(rough_string)
    # Suppress the automatic XML declaration since we write it manually
    pretty_xml = reparsed.toprettyxml(indent="    ", encoding=None)
    # Remove the XML declaration line that toprettyxml adds
    lines = pretty_xml.split('\n')
    if lines and lines[0].startswith('<?xml'):
        return '\n'.join(lines[1:])
    return pretty_xml


def generate_tvshow_nfo(output_path: Path) -> Path:
    """Generate tvshow.nfo for the One Pace series."""
    root = ET.Element("tvshow")

    ET.SubElement(root, "title").text = "One Pace"
    ET.SubElement(root, "originaltitle").text = "One Pace"
    ET.SubElement(root, "sorttitle").text = "One Pace"
    ET.SubElement(root, "plot").text = (
        "One Pace is a fan project that re-edits the One Piece anime to more closely "
        "follow the pacing of the original manga by Eiichiro Oda. The project removes "
        "filler content and padding while maintaining the story's integrity."
    )
    ET.SubElement(root, "genre").text = "Anime"
    ET.SubElement(root, "genre").text = "Action"
    ET.SubElement(root, "genre").text = "Adventure"
    ET.SubElement(root, "studio").text = "One Pace Project"

    nfo_path = output_path / "tvshow.nfo"
    with open(nfo_path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(_prettify_xml(root))

    return nfo_path


def _get_season_number(arc: Arc, arcs: list[Arc]) -> int:
    """Get season number based on slug's position in arc list."""
    # start=1 because most tv shows don't start at season 0.
    for i, a in enumerate(arcs, start=1):
        if a.slug == arc.slug:
            return i
    # Fall back to 1 if it doesn't match for some reason.
    return 1

def generate_episode_nfo(
    arc: Arc,
    episode_number: int,
    video_filename: str,
    output_dir: Path,
    season_number: int | None = None,
    arcs: list[Arc] | None = None,
) -> Path:
    """Generate an episode NFO file."""
    root = ET.Element("episodedetails")

    if season_number is None and arcs is not None:
        season_number = _get_season_number(arc, arcs)
    elif season_number is None:
        season_number = 1

    # Episode title: "Arc Title - Episode Number" or just video filename stem
    episode_title = f"{arc.title} {episode_number:02d}"
    ET.SubElement(root, "title").text = episode_title
    ET.SubElement(root, "showtitle").text = "One Pace"
    ET.SubElement(root, "season").text = str(season_number)
    ET.SubElement(root, "episode").text = str(episode_number)

    # Use arc description as episode plot
    if arc.description:
        ET.SubElement(root, "plot").text = arc.description

    # Add chapter and episode source info
    if arc.chapters:
        ET.SubElement(root, "tag").text = f"Chapters: {arc.chapters}"
    if arc.episodes:
        ET.SubElement(root, "tag").text = f"Episodes: {arc.episodes}"

    # Generate NFO filename based on video filename
    video_path = Path(video_filename)
    nfo_path = output_dir / f"{video_path.stem}.nfo"

    with open(nfo_path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(_prettify_xml(root))

    return nfo_path


def generate_arc_nfos(
    arc: Arc,
    video_files: list[Path],
    output_dir: Path,
    season_number: int | None = None,
    arcs: list[Arc] | None = None
) -> list[Path]:
    """Generate NFO files for all episodes in an arc."""
    nfo_paths = []

    # Sort video files to ensure consistent episode numbering
    sorted_files = sorted(video_files, key=lambda p: p.name)

    for i, video_file in enumerate(sorted_files, start=1):
        nfo_path = generate_episode_nfo(
            arc=arc,
            episode_number=i,
            video_filename=video_file.name,
            output_dir=output_dir,
            season_number=season_number,
            arcs=arcs,
        )
        nfo_paths.append(nfo_path)

    return nfo_paths

"""Utilities for finding and copying poster images."""

import re
import shutil
from pathlib import Path

SUPPORTED_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")


def normalize_slug_for_matching(slug: str) -> str:
    """Convert arc slug to regex pattern for flexible matching.
    
    Allows matching with hyphens, underscores, or spaces as separators.
    Example: 'romance-dawn' matches 'Romance Dawn' and 'romance_dawn'
    
    Args:
        slug: Arc slug (e.g., 'romance-dawn')
    
    Returns:
        Regex pattern string for matching
    """
    # Replace hyphens with pattern that matches hyphen, underscore, or space
    parts = re.split(r'[-_\s]+', slug)
    pattern = r'[-_\s]+'.join(re.escape(part) for part in parts)
    return pattern


def find_poster_for_arc(
    arc_slug: str,
    posters_dir: Path,
    supported_extensions: tuple[str, ...] = SUPPORTED_EXTENSIONS,
) -> Path | None:
    """Find poster image for arc by slug in posters directory.
    
    Matches filenames containing the arc slug with flexible separators.
    Example matches for 'romance-dawn':
    - romance-dawn.jpg
    - Romance Dawn.png
    - romance_dawn_poster.webp
    
    Args:
        arc_slug: Arc slug to match (e.g., 'romance-dawn')
        posters_dir: Directory to search for poster images
        supported_extensions: Tuple of supported image extensions
    
    Returns:
        Path to matching poster, or None if not found
    """
    if not posters_dir.exists() or not posters_dir.is_dir():
        return None
    
    # Build regex pattern for matching
    slug_pattern = normalize_slug_for_matching(arc_slug)
    # Match filename containing the slug pattern (case-insensitive)
    full_pattern = re.compile(rf'.*{slug_pattern}.*', re.IGNORECASE)
    
    # Search for matching files
    for file_path in posters_dir.iterdir():
        if not file_path.is_file():
            continue
        
        # Check extension
        if file_path.suffix.lower() not in supported_extensions:
            continue
        
        # Check filename matches pattern (without extension)
        if full_pattern.match(file_path.stem):
            return file_path
    
    return None


def copy_poster_to_arc_dir(
    poster_source: Path,
    arc_dir: Path,
    target_name: str = "poster.jpg",
) -> Path:
    """Copy poster image to arc directory with standardized naming.
    
    Args:
        poster_source: Source poster file path
        arc_dir: Target arc directory
        target_name: Output filename (default: poster.jpg)
    
    Returns:
        Path to copied poster file
    
    Raises:
        FileNotFoundError: If source poster doesn't exist
        PermissionError: If unable to write to target directory
    """
    if not poster_source.exists():
        raise FileNotFoundError(f"Poster source not found: {poster_source}")
    
    # Create arc directory if it doesn't exist
    arc_dir.mkdir(parents=True, exist_ok=True)
    
    target_path = arc_dir / target_name
    shutil.copy2(poster_source, target_path)
    
    return target_path

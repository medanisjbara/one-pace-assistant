"""PixelDrain download handling."""

import asyncio
from pathlib import Path

import httpx
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TaskID,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from .models import PixelDrainFile, PixelDrainList, Playlist

PIXELDRAIN_API_URL = "https://pixeldrain.com/api"
PIXELDRAIN_DOWNLOAD_URL = "https://pixeldrain.com/api/file"

console = Console()


class DownloadError(Exception):
    """Error during file download."""


async def fetch_playlist_files(playlist: Playlist) -> PixelDrainList:
    """Fetch file list from a PixelDrain playlist."""
    url = f"{PIXELDRAIN_API_URL}/list/{playlist.id}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()

    files = [
        PixelDrainFile(
            id=f["id"],
            name=f["name"],
            size=f["size"],
        )
        for f in data.get("files", [])
    ]

    return PixelDrainList(
        id=data["id"],
        title=data.get("title", ""),
        files=files,
    )


def fetch_playlist_files_sync(playlist: Playlist) -> PixelDrainList:
    """Synchronous version of fetch_playlist_files."""
    url = f"{PIXELDRAIN_API_URL}/list/{playlist.id}"

    with httpx.Client(timeout=30.0) as client:
        response = client.get(url)
        response.raise_for_status()
        data = response.json()

    files = [
        PixelDrainFile(
            id=f["id"],
            name=f["name"],
            size=f["size"],
        )
        for f in data.get("files", [])
    ]

    return PixelDrainList(
        id=data["id"],
        title=data.get("title", ""),
        files=files,
    )


def _get_download_url(file_id: str) -> str:
    """Get the download URL for a PixelDrain file."""
    return f"{PIXELDRAIN_DOWNLOAD_URL}/{file_id}"


async def download_file(
    file: PixelDrainFile,
    output_dir: Path,
    progress: Progress,
    task_id: TaskID,
) -> Path:
    """Download a single file from PixelDrain."""
    output_path = output_dir / file.name

    # Check if file already exists and is complete
    if output_path.exists() and output_path.stat().st_size == file.size:
        progress.update(task_id, completed=file.size)
        return output_path

    url = _get_download_url(file.id)

    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()

            with open(output_path, "wb") as f:
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    f.write(chunk)
                    progress.update(task_id, advance=len(chunk))

    return output_path


def download_file_sync(
    file: PixelDrainFile,
    output_dir: Path,
    progress: Progress,
    task_id: TaskID,
) -> Path:
    """Synchronous version of download_file."""
    output_path = output_dir / file.name

    # Check if file already exists and is complete
    if output_path.exists() and output_path.stat().st_size == file.size:
        progress.update(task_id, completed=file.size)
        return output_path

    url = _get_download_url(file.id)

    with httpx.Client(timeout=None) as client:
        with client.stream("GET", url) as response:
            response.raise_for_status()

            with open(output_path, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=8192):
                    f.write(chunk)
                    progress.update(task_id, advance=len(chunk))

    return output_path


def download_playlist_sync(
    playlist: Playlist,
    output_dir: Path,
    resume: bool = True,
) -> list[Path]:
    """Download all files from a playlist with progress display."""
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Fetch file list
    console.print(f"[cyan]Fetching file list from PixelDrain...[/cyan]")
    file_list = fetch_playlist_files_sync(playlist)

    if not file_list.files:
        console.print("[yellow]No files found in playlist[/yellow]")
        return []

    console.print(f"[green]Found {len(file_list.files)} files to download[/green]")

    downloaded_paths = []

    with Progress(
        TextColumn("[bold blue]{task.fields[filename]}", justify="right"),
        BarColumn(bar_width=None),
        "[progress.percentage]{task.percentage:>3.1f}%",
        "•",
        DownloadColumn(),
        "•",
        TransferSpeedColumn(),
        "•",
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        for file in file_list.files:
            # Check if already downloaded
            output_path = output_dir / file.name
            if resume and output_path.exists() and output_path.stat().st_size == file.size:
                console.print(f"[dim]Skipping (already exists): {file.name}[/dim]")
                downloaded_paths.append(output_path)
                continue

            task_id = progress.add_task(
                "Downloading",
                filename=file.name,
                total=file.size,
            )

            try:
                path = download_file_sync(file, output_dir, progress, task_id)
                downloaded_paths.append(path)
            except Exception as e:
                console.print(f"[red]Error downloading {file.name}: {e}[/red]")
                raise DownloadError(f"Failed to download {file.name}") from e

    return downloaded_paths


def format_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"

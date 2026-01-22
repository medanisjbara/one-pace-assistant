"""PixelDrain download handling."""

import asyncio
import tempfile
import zipfile
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
        download_href=data.get("download_href"),
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


def download_playlist_zip_sync(
    playlist: Playlist,
    output_dir: Path,
    resume: bool = True,
) -> list[Path]:
    """Download all files from a playlist as a single zip archive.
    
    This method downloads the entire playlist as a zip file in a single request,
    avoiding per-file rate limiting that can occur with individual downloads.
    """
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Fetch file list to get download_href and file info
    console.print("[cyan]Fetching playlist info from PixelDrain...[/cyan]")
    file_list = fetch_playlist_files_sync(playlist)

    if not file_list.files:
        console.print("[yellow]No files found in playlist[/yellow]")
        return []

    # Build the zip URL from the list ID
    # The download_href field may not always be present in the API response,
    # so we construct it ourselves based on the verified endpoint pattern
    zip_url = f"https://pixeldrain.com/api/list/{file_list.id}/zip"
    if resume:
        all_exist = True
        for f in file_list.files:
            output_path = output_dir / f.name
            if not (output_path.exists() and output_path.stat().st_size == f.size):
                all_exist = False
                break
        
        if all_exist:
            console.print("[green]All files already downloaded, skipping zip download[/green]")
            return [output_dir / f.name for f in file_list.files]

    console.print(f"[green]Downloading {len(file_list.files)} files as zip archive[/green]")

    # Calculate estimated total size from individual files
    # The actual zip will be slightly larger due to compression overhead,
    # but for video files (already compressed) this is a good estimate
    estimated_total = sum(f.size for f in file_list.files)

    # Download zip to temp file
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp_file:
        tmp_path = Path(tmp_file.name)

    try:
        with Progress(
            TextColumn("[bold blue]Downloading zip", justify="right"),
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
            with httpx.Client(timeout=None) as client:
                with client.stream("GET", zip_url) as response:
                    response.raise_for_status()
                    
                    # Use content-length if available, otherwise use our estimate
                    total_size = int(response.headers.get("content-length", 0)) or estimated_total
                    task_id = progress.add_task("Downloading", total=total_size)

                    with open(tmp_path, "wb") as f:
                        for chunk in response.iter_bytes(chunk_size=8192):
                            f.write(chunk)
                            progress.update(task_id, advance=len(chunk))

        # Extract zip contents
        console.print("[cyan]Extracting files...[/cyan]")
        extracted_paths = []

        with zipfile.ZipFile(tmp_path, "r") as zf:
            for zip_info in zf.infolist():
                if zip_info.is_dir():
                    continue

                # Get just the filename (ignore any directory structure in zip)
                filename = Path(zip_info.filename).name
                output_path = output_dir / filename

                # Skip if file exists with correct size (resume logic)
                if resume and output_path.exists():
                    # Find matching file info for size check
                    matching_file = next(
                        (f for f in file_list.files if f.name == filename), None
                    )
                    if matching_file and output_path.stat().st_size == matching_file.size:
                        console.print(f"[dim]Skipping (already exists): {filename}[/dim]")
                        extracted_paths.append(output_path)
                        continue

                # Extract file
                with zf.open(zip_info) as src, open(output_path, "wb") as dst:
                    dst.write(src.read())
                extracted_paths.append(output_path)

        console.print(f"[green]Extracted {len(extracted_paths)} files[/green]")
        return extracted_paths

    except httpx.HTTPStatusError as e:
        raise DownloadError(f"Failed to download zip: {e}") from e
    finally:
        # Cleanup temp file
        if tmp_path.exists():
            tmp_path.unlink()


def format_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"

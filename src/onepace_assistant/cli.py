"""CLI interface for One Pace Assistant."""

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from . import __version__
from .downloader import download_playlist_sync, fetch_playlist_files_sync, format_size
from .nfo import generate_arc_nfos, generate_tvshow_nfo
from .scraper import fetch_metadata_sync, ScraperError

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="onepace")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
@click.option("-q", "--quiet", is_flag=True, help="Suppress non-essential output")
@click.pass_context
def cli(ctx: click.Context, verbose: bool, quiet: bool) -> None:
    """One Pace Assistant - Download and organize One Pace files."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["quiet"] = quiet


@cli.command()
@click.option("-a", "--all", "include_all", is_flag=True, help="Include specials and side stories")
@click.option(
    "-f",
    "--format",
    "output_format",
    type=click.Choice(["table", "json", "plain"]),
    default="table",
    help="Output format",
)
@click.pass_context
def list(ctx: click.Context, include_all: bool, output_format: str) -> None:
    """List available arcs."""
    try:
        arcs = fetch_metadata_sync()
    except ScraperError as e:
        console.print(f"[red]Error fetching metadata: {e}[/red]")
        raise SystemExit(1)

    # Filter specials if not including all
    if not include_all:
        arcs = [a for a in arcs if not a.special]

    if output_format == "json":
        import json

        arc_data = [
            {
                "slug": a.slug,
                "title": a.title,
                "special": a.special,
                "chapters": a.chapters,
                "episodes": a.episodes,
                "resolutions": sorted(a.available_resolutions()),
            }
            for a in arcs
        ]
        click.echo(json.dumps(arc_data, indent=2))

    elif output_format == "plain":
        for arc in arcs:
            click.echo(f"{arc.slug}\t{arc.title}")

    else:  # table
        table = Table(title="One Pace Arcs")
        table.add_column("Slug", style="cyan")
        table.add_column("Title", style="bold")
        table.add_column("Chapters")
        table.add_column("Resolutions")

        for arc in arcs:
            resolutions = ", ".join(f"{r}p" for r in sorted(arc.available_resolutions()))
            table.add_row(
                arc.slug,
                arc.title,
                arc.chapters or "-",
                resolutions or "-",
            )

        console.print(table)


@cli.command()
@click.argument("arc_slug")
@click.pass_context
def info(ctx: click.Context, arc_slug: str) -> None:
    """Show detailed information about an arc."""
    try:
        arcs = fetch_metadata_sync()
    except ScraperError as e:
        console.print(f"[red]Error fetching metadata: {e}[/red]")
        raise SystemExit(1)

    # Find the arc
    arc = next((a for a in arcs if a.slug == arc_slug), None)
    if not arc:
        console.print(f"[red]Arc '{arc_slug}' not found[/red]")
        console.print("[dim]Use 'onepace list' to see available arcs[/dim]")
        raise SystemExit(1)

    # Display arc info
    console.print(f"\n[bold cyan]{arc.title}[/bold cyan]")
    console.print(f"[dim]Slug: {arc.slug}[/dim]\n")

    if arc.description:
        console.print(f"[italic]{arc.description}[/italic]\n")

    if arc.chapters:
        console.print(f"📖 Manga Chapters: {arc.chapters}")
    if arc.episodes:
        console.print(f"📺 Anime Episodes: {arc.episodes}")

    # Resolutions
    resolutions = sorted(arc.available_resolutions(), reverse=True)
    console.print(f"🎬 Resolutions: {', '.join(f'{r}p' for r in resolutions)}")

    # Language options
    console.print("\n[bold]Available Variants:[/bold]")
    for lang in arc.available_languages():
        variant = f" ({lang['variant']})" if lang.get("variant") else ""
        sub = lang.get("sub") or "none"
        dub = lang.get("dub") or "unknown"
        console.print(f"  • Sub: {sub}, Dub: {dub}{variant}")


@cli.command()
@click.argument("arc_slug")
@click.option(
    "-o",
    "--output",
    "output_dir",
    type=click.Path(path_type=Path),
    default=Path("./downloads"),
    help="Output directory",
)
@click.option(
    "-r",
    "--resolution",
    type=click.Choice(["480", "720", "1080"]),
    default="1080",
    help="Video resolution",
)
@click.option("-s", "--sub", default=None, help="Subtitle language (en, none, or omit for auto)")
@click.option("-d", "--dub", default="ja", help="Audio language (ja, en)")
@click.option("-n", "--dry-run", is_flag=True, help="Show what would be downloaded")
@click.option("--no-nfo", is_flag=True, help="Skip NFO file generation")
@click.option("--resume/--no-resume", default=True, help="Resume interrupted downloads")
@click.pass_context
def download(
    ctx: click.Context,
    arc_slug: str,
    output_dir: Path,
    resolution: str,
    sub: str,
    dub: str,
    dry_run: bool,
    no_nfo: bool,
    resume: bool,
) -> None:
    """Download an arc."""
    quiet = ctx.obj.get("quiet", False)

    # Fetch metadata
    if not quiet:
        console.print("[cyan]Fetching arc metadata...[/cyan]")

    try:
        arcs = fetch_metadata_sync()
    except ScraperError as e:
        console.print(f"[red]Error fetching metadata: {e}[/red]")
        raise SystemExit(1)

    # Find the arc
    arc = next((a for a in arcs if a.slug == arc_slug), None)
    if not arc:
        console.print(f"[red]Arc '{arc_slug}' not found[/red]")
        console.print("[dim]Use 'onepace list' to see available arcs[/dim]")
        raise SystemExit(1)

    # Handle subtitle preference with smart defaults
    playlist = None
    actual_sub = None  # Track what was actually selected
    
    if sub is None:
        # Auto-detect based on dub language
        if dub == "en":
            # Try English dub without subs first, fall back to with subs
            playlist = arc.get_playlist(resolution=int(resolution), sub=None, dub=dub)
            if playlist:
                actual_sub = "none"
            else:
                playlist = arc.get_playlist(resolution=int(resolution), sub="en", dub=dub)
                if playlist:
                    actual_sub = "en"
        else:
            # For non-English dubs, default to English subs
            playlist = arc.get_playlist(resolution=int(resolution), sub="en", dub=dub)
            if playlist:
                actual_sub = "en"
    else:
        # User explicitly specified subtitle preference
        sub_pref = None if sub.lower() == "none" else sub
        playlist = arc.get_playlist(resolution=int(resolution), sub=sub_pref, dub=dub)
        actual_sub = sub

    if not playlist:
        console.print(f"[red]No playlist found matching preferences[/red]")
        console.print("[dim]Try 'onepace info {arc_slug}' to see available options[/dim]")
        raise SystemExit(1)

    if not quiet:
        console.print(f"[green]Found: {arc.title}[/green]")
        console.print(f"[dim]Resolution: {playlist.resolution}p, Sub: {actual_sub}, Dub: {dub}[/dim]")

    # Dry run
    if dry_run:
        console.print("\n[yellow]DRY RUN - No files will be downloaded[/yellow]\n")

        file_list = fetch_playlist_files_sync(playlist)
        total_size = sum(f.size for f in file_list.files)

        table = Table(title="Files to Download")
        table.add_column("Filename")
        table.add_column("Size", justify="right")

        for f in file_list.files:
            table.add_row(f.name, format_size(f.size))

        console.print(table)
        console.print(f"\n[bold]Total: {len(file_list.files)} files, {format_size(total_size)}[/bold]")
        return

    # Create output directory
    arc_output_dir = output_dir / arc.slug
    arc_output_dir.mkdir(parents=True, exist_ok=True)

    if not quiet:
        console.print(f"[dim]Output: {arc_output_dir}[/dim]\n")

    # Download files
    try:
        downloaded_files = download_playlist_sync(playlist, arc_output_dir, resume=resume)
    except Exception as e:
        console.print(f"[red]Download failed: {e}[/red]")
        raise SystemExit(1)

    # Generate NFO files
    if not no_nfo and downloaded_files:
        if not quiet:
            console.print("\n[cyan]Generating NFO files...[/cyan]")

        # Generate tvshow.nfo in parent directory
        generate_tvshow_nfo(output_dir)

        # Generate episode NFOs
        video_files = [f for f in downloaded_files if f.suffix.lower() in (".mkv", ".mp4", ".avi")]
        generate_arc_nfos(arc, video_files, arc_output_dir)

        if not quiet:
            console.print(f"[green]Generated {len(video_files) + 1} NFO files[/green]")

    console.print(f"\n[bold green]✓ Download complete![/bold green]")
    console.print(f"[dim]Files saved to: {arc_output_dir}[/dim]")


def main() -> None:
    """Entry point for the CLI."""
    cli(obj={})


if __name__ == "__main__":
    main()

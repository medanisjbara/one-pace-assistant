# One Pace Assistant

A CLI tool to download and organize [One Pace](https://onepace.net) files for media servers like Plex, Jellyfin, and Emby.

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/one-pace-assistant.git
cd one-pace-assistant

# Install with pip (editable mode for development)
pip install -e .

# Or install with dev dependencies
pip install -e ".[dev]"
```

## Usage

### List Available Arcs

```bash
onepace list                      # List main arcs
onepace list --all                # Include specials
onepace list --format json        # JSON output for scripting
```

### Download Content

```bash
# Download an arc at 1080p (default)
onepace download romance-dawn

# Preview what would be downloaded
onepace download wano --dry-run

# Custom output directory and resolution
onepace download -o ~/media/anime -r 720 alabasta

# English dub version
onepace download romance-dawn --dub en --sub none
```

### Get Arc Information

```bash
onepace info romance-dawn
```

## Media Server Setup

### Jellyfin / Emby

NFO files are automatically generated alongside downloads. Your media server should pick up the metadata automatically.

### Plex

Plex requires the [XBMCnfoTVImporter](https://github.com/gboudreau/XBMCnfoTVImporter.bundle) agent to read NFO files. Follow the installation instructions in that repository.

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linter
ruff check .
```

## License

MIT

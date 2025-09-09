# Discogs to Tidal Sync

A modern Python application that syncs your Discogs collection to Tidal playlists with advanced search optimization and comprehensive testing.

## ✨ Features

- **Smart Collection Sync**: Fetch albums from your Discogs collection and create corresponding Tidal playlists
- **Style-Based Organization**: Automatically create playlists organized by styles/subgenres (e.g., "House", "Deep House", "Techno")
- **Multi-Playlist Support**: Tracks from albums with multiple styles are added to all relevant playlists
- **Folder Support**: Organize sync by specific Discogs folders
- **Advanced Search**: Intelligent matching between Discogs and Tidal tracks with fallback strategies
- **Progress Tracking**: Real-time sync progress with detailed reporting
- **Comprehensive Testing**: 134+ unit tests with 100% coverage of core functionality
- **Modern Architecture**: Clean, maintainable code following Python best practices
- **CLI Interface**: User-friendly command-line interface with authentication flow

## 🚀 Quick Start

### Prerequisites
- Python 3.8+ (tested with Python 3.11)
- Discogs API token
- Tidal account

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/anneoneone/discogs_to_tidal.git
   cd discogs_to_tidal
   ```

2. **Create virtual environment** (recommended):
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install the package in development mode**:
   ```bash
   pip install -e ".[dev]"
   ```

### Configuration

1. **Get your Discogs API token**:
   - Go to [Discogs Settings](https://www.discogs.com/settings/developers)
   - Generate a new token

2. **Run the sync**:
   ```bash
   discogs-to-tidal
   ```
   Or alternatively:
   ```bash
   python -m discogs_to_tidal.cli
   ```

You'll be prompted to enter your Discogs token and authenticate with Tidal on first run.

## 📖 Usage

### Basic Sync
Sync your entire collection to a single playlist:
```bash
discogs-to-tidal sync --playlist-name "My Collection"
```

### Style-Based Sync (New!)
Create multiple playlists organized by styles/subgenres:
```bash
# Create playlists like "Discogs - House", "Discogs - Techno", etc.
discogs-to-tidal style-sync

# Custom base name: "MyMusic - House", "MyMusic - Techno", etc.
discogs-to-tidal style-sync --base-name "MyMusic"

# Limit processing and specify folder
discogs-to-tidal style-sync --base-name "Electronic" --folder-id 123 --limit 100
```

### Advanced Options
```bash
# Sync specific folder with dry-run
discogs-to-tidal sync --folder-id 123456 --limit 50 --dry-run

# Interactive folder selection
discogs-to-tidal sync  # Will prompt for folder selection

# List available folders
discogs-to-tidal list-folders

# Authentication commands
discogs-to-tidal tidal-auth    # Authenticate with Tidal
discogs-to-tidal discogs-auth  # Set up Discogs token
discogs-to-tidal test-auth     # Test both authentications
```

### Style-Based Organization Features
- **Multiple Playlists**: Creates separate playlists for each style found in your collection
- **Multi-Style Support**: Tracks from albums with multiple styles (e.g., ["House", "Deep House"]) are added to all relevant playlists
- **Optimized Search**: Each track is searched on Tidal only once, then cached and reused for multiple playlists (major performance improvement!)
- **Unknown Style Handling**: Tracks without style information are grouped into an "Unknown Style" playlist
- **Customizable Naming**: Control the base name for all generated playlists
- **Batch Operations**: Uses efficient batch playlist operations when possible

## 🏗️ Development

### Modern Python Setup
This project uses modern Python packaging with `pyproject.toml`:

```bash
# Install for development
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=src --cov-report=html

# Code formatting
black src tests
isort src tests

# Linting
flake8 src tests
mypy src
```

### Project Structure
```
discogs_to_tidal/
├── src/discogs_to_tidal/           # Main package
│   ├── cli/                        # Command-line interface
│   ├── core/                       # Core business logic
│   │   ├── config.py              # Configuration management
│   │   ├── models.py              # Data models
│   │   ├── sync.py                # Sync orchestration
│   │   └── exceptions.py          # Custom exceptions
│   ├── integrations/              # External API integrations
│   │   ├── discogs/               # Discogs API client
│   │   └── tidal/                 # Tidal API client
│   ├── storage/                   # Data persistence
│   └── utils/                     # Utility functions
├── tests/                         # Test suite (134+ tests)
│   ├── unit/                      # Unit tests
│   └── integration/               # Integration tests
├── pyproject.toml                 # Modern Python configuration
└── README.md                      # This file
```

### Testing
- **134 tests** covering all core functionality
- **Unit tests** for models, configuration, and sync logic
- **Integration tests** for end-to-end workflows
- **Mock-based testing** for external API interactions

## 🔧 Configuration

### Environment Variables
You can configure the application using environment variables:

```bash
export DISCOGS_TOKEN="your_discogs_token_here"
export OUTPUT_DIR="/path/to/output"  # Optional: defaults to ./output
```

### Configuration File
The app automatically creates a `.env` file to store your settings after the first run.

## 📊 Output

The sync process generates detailed reports:
- **JSON output**: Complete sync results in `output/discogs_to_tidal_conversion.json`
- **Progress tracking**: Real-time updates during the sync process
- **Match statistics**: Success rates and detailed matching information

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes following the existing code style
4. Run tests: `pytest`
5. Run linting: `black src tests && flake8 src tests`
6. Commit your changes: `git commit -m 'Add amazing feature'`
7. Push to the branch: `git push origin feature/amazing-feature`
8. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## ⚠️ Disclaimer

This project uses unofficial Tidal APIs. Use at your own risk. The authors are not responsible for any issues that may arise from using this software.

## 🙏 Acknowledgments

- [Discogs API](https://www.discogs.com/developers/) for providing access to music collection data
- [TidalAPI](https://github.com/tamland/python-tidal) community for the Python Tidal integration
- All contributors who help improve this project

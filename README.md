# Discogs to Tidal Sync

A modern Python application that syncs your Discogs collection to Tidal playlists with advanced search optimization and comprehensive testing.

## ✨ Features

- **Smart Collection Sync**: Fetch albums from your Discogs collection and create corresponding Tidal playlists
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
```bash
discogs-to-tidal
```

### Advanced Options
The application supports various configuration options through environment variables or interactive prompts:

- **Discogs Token**: Your personal API token from Discogs
- **Folder Selection**: Choose specific folders from your collection
- **Playlist Management**: Create new or update existing playlists
- **Output Options**: Configure result reporting and logging

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

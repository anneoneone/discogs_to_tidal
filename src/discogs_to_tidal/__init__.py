"""
Discogs to Tidal Sync - A tool to sync your Discogs collection to Tidal playlists.

This package provides functionality to:
- Fetch tracks from your Discogs collection
- Search for matching tracks on Tidal
- Create and manage Tidal playlists
- Sync collections between the two services

Example:
    Basic usage from command line:

    $ discogs-to-tidal sync --playlist "My Collection"

    Programmatic usage:

    >>> from discogs_to_tidal import DiscogsService, TidalService, Config
    >>> config = Config.from_env()
    >>> discogs = DiscogsService(config)
    >>> tidal = TidalService(config)
    >>> tracks = discogs.get_collection_tracks()
    >>> result = tidal.add_tracks_to_playlist("My Playlist", tracks)
"""

__version__ = "0.2.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"
__license__ = "MIT"

# CLI interface
from .cli import cli
from .core.config import Config
from .core.exceptions import (
    AuthenticationError,
    ConfigurationError,
    DiscogsToTidalError,
    RateLimitError,
    SearchError,
    StorageError,
    SyncError,
)
from .core.models import Album, Artist, Playlist, SyncResult, Track

# Integration services
from .integrations import DiscogsService, TidalService

__all__ = [
    "__version__",
    "Config",
    "Track",
    "Album",
    "Artist",
    "Playlist",
    "SyncResult",
    "DiscogsToTidalError",
    "AuthenticationError",
    "SearchError",
    "SyncError",
    "ConfigurationError",
    "StorageError",
    "RateLimitError",
    "DiscogsService",
    "TidalService",
    "cli",
]

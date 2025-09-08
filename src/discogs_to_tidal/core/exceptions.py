"""
Custom exceptions for the discogs_to_tidal package.
"""


class DiscogsToTidalError(Exception):
    """Base exception for all discogs_to_tidal errors."""
    pass


class AuthenticationError(DiscogsToTidalError):
    """Raised when authentication fails for Discogs or Tidal."""
    pass


class SearchError(DiscogsToTidalError):
    """Raised when track search fails."""
    pass


class SyncError(DiscogsToTidalError):
    """Raised when synchronization fails."""
    pass


class ConfigurationError(DiscogsToTidalError):
    """Raised when configuration is invalid."""
    pass


class StorageError(DiscogsToTidalError):
    """Raised when storage operations fail."""
    pass


class RateLimitError(DiscogsToTidalError):
    """Raised when API rate limits are exceeded."""
    pass

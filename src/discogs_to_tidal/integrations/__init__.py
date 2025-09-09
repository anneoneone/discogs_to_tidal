"""
Integration packages for external services.
"""
from .discogs import DiscogsService
from .tidal import TidalAuth, TidalSearchService, TidalService

__all__ = ["DiscogsService", "TidalService", "TidalAuth", "TidalSearchService"]

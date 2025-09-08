"""
Integration packages for external services.
"""
from .discogs import DiscogsService
from .tidal import TidalService, TidalAuth, TidalSearchService

__all__ = ['DiscogsService', 'TidalService', 'TidalAuth', 'TidalSearchService']

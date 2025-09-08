"""
Tidal integration package.
"""
from .auth import TidalAuth
from .client import TidalService
from .search import TidalSearchService

__all__ = ['TidalAuth', 'TidalService', 'TidalSearchService']

"""
Tidal API client for playlist management.
"""
import logging
from typing import List, Optional

import tidalapi

from ...core.models import Track, SyncResult
from ...core.exceptions import SyncError
from ...core.config import Config
from .auth import TidalAuth
from .search import TidalSearchService

logger = logging.getLogger(__name__)


class TidalService:
    """Service for interacting with Tidal API."""
    
    def __init__(self, config: Config):
        self.config = config
        self._auth = TidalAuth(config)
        self._search_service: Optional[TidalSearchService] = None
        self._session: Optional[tidalapi.Session] = None
    
    @property
    def session(self) -> tidalapi.Session:
        """Get authenticated Tidal session."""
        if self._session is None:
            self._session = self._auth.authenticate()
        return self._session
    
    def authenticate_with_progress(self, progress_callback=None) -> tidalapi.Session:
        """
        Authenticate with optional progress callback for better UX.
        
        Args:
            progress_callback: Function called with (message, progress_percent)
            
        Returns:
            Authenticated Tidal session
        """
        if progress_callback:
            self._auth.set_progress_callback(progress_callback)
        
        self._session = self._auth.authenticate()
        return self._session
    
    def is_authenticated(self) -> bool:
        """Check if already authenticated without triggering login."""
        if self._session:
            return self._auth.validate_session(self._session)
        
        # Try to load existing session without creating new one
        session_data = self._auth.load_session()
        if session_data:
            try:
                test_session = tidalapi.Session()
                test_session.load_oauth_session(
                    session_data.get("token_type"),
                    session_data.get("access_token"),
                    session_data.get("refresh_token")
                )
                return self._auth.validate_session(test_session)
            except Exception:
                return False
        
        return False
    
    def logout(self) -> bool:
        """Clear authentication and saved tokens."""
        self._session = None
        return self._auth.clear_session()
    
    @property
    def search_service(self) -> TidalSearchService:
        """Get search service instance."""
        if self._search_service is None:
            self._search_service = TidalSearchService(self.session)
        return self._search_service
    
    def create_or_get_playlist(
        self, name: str, description: str = ""
    ) -> tidalapi.Playlist:
        """
        Create a new playlist or get existing one by name.
        
        Args:
            name: Playlist name
            description: Playlist description for new playlists
            
        Returns:
            Tidal playlist object
        """
        logger.info("Fetching your Tidal playlists...")
        
        try:
            playlists = self.session.user.playlists()
        except Exception as e:
            logger.error(f"Error fetching playlists: {e}")
            playlists = []
        
        # Look for existing playlist
        for playlist in playlists:
            if hasattr(playlist, 'name') and playlist.name == name:
                logger.info(f"Found existing playlist: {name}")
                return playlist
        
        # Create new playlist
        logger.info(f"Creating new playlist: {name}")
        try:
            playlist = self.session.user.create_playlist(name, description)
            return playlist
        except Exception as e:
            raise SyncError(f"Failed to create playlist '{name}': {e}")
    
    def add_tracks_to_playlist(
        self, playlist_name: str, tracks: List[Track]
    ) -> SyncResult:
        """
        Add tracks to a Tidal playlist.
        
        Args:
            playlist_name: Name of the playlist
            tracks: List of tracks to add
            
        Returns:
            Sync result with statistics
        """
        if not tracks:
            logger.warning("No tracks provided")
            return SyncResult(
                total_tracks=0,
                found_tracks=0,
                added_tracks=0,
                failed_tracks=0
            )
        
        # Get or create playlist
        description = f"Imported from Discogs - {len(tracks)} tracks"
        playlist = self.create_or_get_playlist(playlist_name, description)
        
        logger.info(f"Adding {len(tracks)} tracks to playlist '{playlist_name}'...")
        
        added_count = 0
        failed_count = 0
        found_tracks = []
        
        for idx, track in enumerate(tracks, 1):
            if not track.title or not track.primary_artist:
                logger.warning(
                    f"Skipping track {idx} with missing title or artist: {track}"
                )
                failed_count += 1
                continue
            
            logger.info(
                f"Track {idx}/{len(tracks)}: {track.title} "
                f"by {track.primary_artist.name}"
            )
            
            # Search for track on Tidal
            tidal_track = self.search_service.find_track(track)
            
            if tidal_track:
                try:
                    playlist.add([tidal_track.id])
                    added_count += 1
                    found_tracks.append(track)
                    logger.info(
                        f"    Added: {track.title} by {track.primary_artist.name}"
                    )
                except Exception as e:
                    logger.error(
                        f"    Failed to add track to playlist: {e}"
                    )
                    failed_count += 1
            else:
                failed_count += 1
        
        result = SyncResult(
            total_tracks=len(tracks),
            found_tracks=len(found_tracks),
            added_tracks=added_count,
            failed_tracks=failed_count
        )
        
        logger.info(
            f"Finished adding tracks to playlist. "
            f"Total: {result.total_tracks}, "
            f"Found: {result.found_tracks}, "
            f"Added: {result.added_tracks}, "
            f"Failed: {result.failed_tracks}"
        )
        
        return result

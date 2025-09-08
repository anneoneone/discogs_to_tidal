"""
Discogs API client for fetching collection data.
"""
import logging
import time
from typing import List, Optional, Dict, Any, Callable

from discogs_client import Client as DiscogsClient

from ...core.models import Track, Album, Artist
from ...core.exceptions import AuthenticationError, SearchError
from ...core.config import Config
from .auth import DiscogsAuth, DiscogsAuthMethod, DiscogsAuthStatus

logger = logging.getLogger(__name__)


class DiscogsService:
    """Service for interacting with the Discogs API with improved authentication."""
    
    def __init__(self, config: Config):
        self.config = config
        self._auth = DiscogsAuth(config)
        self._client: Optional[DiscogsClient] = None
        self._user = None
    
    @property
    def client(self) -> DiscogsClient:
        """Get authenticated Discogs client."""
        if self._client is None:
            self._client = self._auth.authenticate()
        return self._client
    
    @property
    def user(self):
        """Get authenticated user info."""
        if self._user is None:
            self._user = self._auth.user
        return self._user
    
    def authenticate(self) -> None:
        """Authenticate with Discogs using the refactored auth system."""
        try:
            self._client = self._auth.authenticate()
            self._user = self._auth.user
            logger.info(f"Authenticated as Discogs user: {self._user.username}")
        except Exception as e:
            raise AuthenticationError(f"Discogs authentication failed: {e}")
    
    def authenticate_with_progress(
        self, 
        progress_callback: Callable[[str, int], None]
    ) -> bool:
        """
        Authenticate with progress feedback.
        
        Args:
            progress_callback: Function to call with progress updates
            
        Returns:
            True if authentication successful, False otherwise
        """
        try:
            self._auth.set_progress_callback(progress_callback)
            self._client = self._auth.authenticate()
            self._user = self._auth.user
            return True
        except Exception as e:
            logger.error(f"Discogs authentication failed: {e}")
            return False
    
    def is_authenticated(self) -> bool:
        """Check if currently authenticated with Discogs."""
        return self._auth.is_authenticated()
    
    def get_auth_status(self) -> DiscogsAuthStatus:
        """Get current authentication status."""
        return self._auth.get_auth_status()
    
    def logout(self) -> bool:
        """Clear current authentication session."""
        success = self._auth.logout()
        if success:
            self._client = None
            self._user = None
        return success
    
    def get_collection_tracks(self, folder_id: int = 0) -> List[Track]:
        """
        Get all tracks from user's Discogs collection.
        
        Args:
            folder_id: Collection folder ID (0 = default "All" folder)
            
        Returns:
            List of Track objects
        """
        if self._user is None:
            self.authenticate()
        
        logger.info(f"Fetching tracks from collection folder {folder_id}")
        tracks = []
        
        try:
            folder = self._user.collection_folders[folder_id]
            releases = list(folder.releases)
            
            logger.info(f"Found {len(releases)} releases in collection")
            
            for i, release in enumerate(releases, 1):
                if self.config.max_tracks > 0 and len(tracks) >= self.config.max_tracks:
                    logger.info(f"Reached max_tracks limit ({self.config.max_tracks})")
                    break
                
                try:
                    release_tracks = self._process_release(
                        release.release, i, len(releases)
                    )
                    tracks.extend(release_tracks)
                    
                    # Rate limiting
                    time.sleep(0.2)
                    
                except Exception as e:
                    logger.warning(f"Failed to process release {i}: {e}")
                    continue
            
            logger.info(f"Total tracks fetched: {len(tracks)}")
            return tracks
            
        except Exception as e:
            raise SearchError(f"Failed to fetch collection: {e}")
    
    def _process_release(
        self, release, release_num: int, total_releases: int
    ) -> List[Track]:
        """Process a single release and extract tracks."""
        logger.info(
            f"Processing release {release_num}/{total_releases}: {release.title}"
        )
        
        tracks = []
        release_data = release.data
        
        # Get release-level artists
        release_artists = self._extract_artists(release_data.get('artists', []))
        
        # Create album object
        album = Album(
            title=release.title,
            artists=release_artists,
            year=release_data.get('year'),
            id=str(release.id),
            genres=release_data.get('genres', [])
        )
        
        # Process each track
        for track_data in release.tracklist:
            try:
                track = self._create_track_from_data(
                    track_data.data, album, release_artists
                )
                if track:
                    tracks.append(track)
                    logger.debug(
                        f"  Found track: {track.title} by {track.primary_artist}"
                    )
            except Exception as e:
                logger.warning(f"Failed to process track: {e}")
                continue
        
        return tracks
    
    def _create_track_from_data(
        self, track_data: Dict[str, Any], album: Album,
        fallback_artists: List[Artist]
    ) -> Optional[Track]:
        """Create a Track object from Discogs track data."""
        title = track_data.get('title')
        if not title:
            return None
        
        # Get track-specific artists or fall back to release artists
        track_artists = self._extract_artists(track_data.get('artists', []))
        if not track_artists:
            track_artists = fallback_artists
        
        # Parse duration (format: "MM:SS")
        duration = None
        duration_str = track_data.get('duration', '')
        if duration_str:
            try:
                if ':' in duration_str:
                    minutes, seconds = duration_str.split(':')
                    duration = int(minutes) * 60 + int(seconds)
            except (ValueError, IndexError):
                pass
        
        return Track(
            title=title,
            artists=track_artists,
            album=album,
            duration=duration,
            track_number=self._parse_position(track_data.get('position', '')),
            id=track_data.get('id')
        )
    
    def _extract_artists(self, artists_data: List[Dict[str, Any]]) -> List[Artist]:
        """Extract Artist objects from Discogs artist data."""
        artists = []
        for artist_data in artists_data:
            name = artist_data.get('name')
            if name:
                artist = Artist(
                    name=name,
                    id=str(artist_data.get('id', ''))
                )
                artists.append(artist)
        return artists
    
    def _parse_position(self, position_str: str) -> Optional[int]:
        """Parse track position string to track number."""
        if not position_str:
            return None
        
        try:
            # Handle formats like "A1", "1", "B2", etc.
            # Extract numeric part
            numeric_part = ''.join(c for c in position_str if c.isdigit())
            if numeric_part:
                return int(numeric_part)
        except ValueError:
            pass
        
        return None

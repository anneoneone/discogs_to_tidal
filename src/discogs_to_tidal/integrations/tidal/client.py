"""
Tidal API client for playlist management.
"""
import logging
from typing import Any, Callable, Dict, List, Optional

import tidalapi

from ...core.config import Config
from ...core.exceptions import SyncError
from ...core.models import SyncResult, Track
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

    def authenticate_with_progress(
        self, progress_callback: Optional[Callable] = None
    ) -> tidalapi.Session:
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
                token_type = session_data.get("token_type") or ""
                access_token = session_data.get("access_token") or ""
                refresh_token = session_data.get("refresh_token") or ""
                test_session.load_oauth_session(
                    token_type,
                    access_token,
                    refresh_token,
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
            playlists = self.session.user.playlists()  # type: ignore[union-attr]
        except Exception as e:
            logger.error(f"Error fetching playlists: {e}")
            playlists = []

        # Look for existing playlist
        for playlist in playlists:
            if hasattr(playlist, "name") and playlist.name == name:
                logger.info(f"Found existing playlist: {name}")
                return playlist  # type: ignore[no-any-return]

        # Create new playlist
        logger.info(f"Creating new playlist: {name}")
        try:
            playlist = self.session.user.create_playlist(  # type: ignore[union-attr]
                name, description
            )
            return playlist  # type: ignore[no-any-return]
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
                success=True,
                total_tracks=0,
                matched_tracks=0,
                failed_tracks=0,
                playlist_name=playlist_name,
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
                    playlist.add([tidal_track.id])  # type: ignore[attr-defined]
                    added_count += 1
                    found_tracks.append(track)
                    logger.info(
                        f"    Added: {track.title} by {track.primary_artist.name}"
                    )
                except Exception as e:
                    logger.error(f"    Failed to add track to playlist: {e}")
                    failed_count += 1
            else:
                failed_count += 1

        result = SyncResult(
            success=added_count > 0,
            total_tracks=len(tracks),
            matched_tracks=len(found_tracks),
            failed_tracks=failed_count,
            playlist_name=playlist_name,
        )

        logger.info(
            f"Finished adding tracks to playlist. "
            f"Total: {result.total_tracks}, "
            f"Found: {result.found_tracks}, "
            f"Added: {result.added_tracks}, "
            f"Failed: {result.failed_tracks}"
        )

        return result

    def create_style_based_playlists(
        self, tracks: List[Track], base_playlist_name: str = "Discogs"
    ) -> Dict[str, SyncResult]:
        """
        Create Tidal playlists based on styles and add tracks to appropriate playlists.

        Optimized version that searches each track only once and caches results.
        If a track's album has multiple styles, the track will be added to
        multiple playlists using the cached Tidal track.

        Args:
            tracks: List of tracks to organize by style
            base_playlist_name: Base name for playlists (e.g., "Discogs - House")

        Returns:
            Dictionary mapping style names to sync results
        """
        if not tracks:
            logger.warning("No tracks provided")
            return {}

        # Cache existing playlists to avoid repeated API calls
        logger.info("📋 Fetching existing Tidal playlists...")
        existing_playlists = self._get_all_playlists()
        playlist_cache: Dict[str, Any] = {
            playlist.name: playlist
            for playlist in existing_playlists
            if hasattr(playlist, "name")
        }
        logger.info(f"Found {len(playlist_cache)} existing playlists")

        # First pass: search for all tracks on Tidal and cache results
        logger.info(f"🔍 Searching for {len(tracks)} tracks on Tidal...")
        track_cache: Dict[str, Optional[Any]] = {}  # Track ID -> Tidal track object

        for i, track in enumerate(tracks, 1):
            if not track.title or not track.primary_artist:
                logger.debug(
                    f"Skipping track {i} with missing title or artist: {track}"
                )
                track_cache[self._get_track_key(track)] = None
                continue

            logger.debug(
                f"Searching track {i}/{len(tracks)}: {track.title} "
                f"by {track.primary_artist.name}"
            )

            # Search for track on Tidal only once
            tidal_track = self.search_service.find_track(track)
            track_cache[self._get_track_key(track)] = tidal_track

        # Count successful searches
        found_tracks = sum(1 for t in track_cache.values() if t is not None)
        logger.info(
            f"✅ Search complete: {found_tracks}/{len(tracks)} tracks found on Tidal"
        )

        # Second pass: group tracks by style using cached search results
        style_tracks: Dict[str, List[Track]] = {}
        style_tidal_tracks: Dict[str, List[Any]] = {}  # Style -> Tidal track objects
        tracks_without_styles = []
        tracks_without_styles_tidal = []

        for track in tracks:
            track_key = self._get_track_key(track)
            tidal_track = track_cache.get(track_key)

            if track.album and track.album.styles:
                # Add track to each style playlist
                for style in track.album.styles:
                    if style not in style_tracks:
                        style_tracks[style] = []
                        style_tidal_tracks[style] = []

                    style_tracks[style].append(track)
                    # Only add if we found it on Tidal
                    if tidal_track:
                        style_tidal_tracks[style].append(tidal_track)
            else:
                tracks_without_styles.append(track)
                if tidal_track:
                    tracks_without_styles_tidal.append(tidal_track)

        logger.info(f"Found {len(style_tracks)} different styles")
        logger.info(f"Found {len(tracks_without_styles)} tracks without styles")

        # Third pass: create playlists and add cached tracks
        results: Dict[str, SyncResult] = {}

        for style, style_track_list in style_tracks.items():
            playlist_name = f"{base_playlist_name} - {style}"
            tidal_tracks_for_style = style_tidal_tracks[style]

            logger.info(
                f"Creating playlist for style '{style}' with "
                f"{len(style_track_list)} tracks ({len(tidal_tracks_for_style)} found)"
            )

            # Create playlist using cached playlist data
            playlist = self._create_or_get_cached_playlist(
                playlist_name, playlist_cache
            )

            # Add tracks directly using cached Tidal tracks
            result = self._add_cached_tracks_to_playlist_direct(
                playlist, playlist_name, style_track_list, tidal_tracks_for_style
            )
            results[style] = result

        # Handle tracks without styles
        if tracks_without_styles:
            unknown_playlist_name = f"{base_playlist_name} - Unknown Style"
            logger.info(
                f"Creating playlist for tracks without styles: "
                f"{len(tracks_without_styles)} tracks "
                f"({len(tracks_without_styles_tidal)} found)"
            )

            playlist = self._create_or_get_cached_playlist(
                unknown_playlist_name, playlist_cache
            )

            result = self._add_cached_tracks_to_playlist_direct(
                playlist,
                unknown_playlist_name,
                tracks_without_styles,
                tracks_without_styles_tidal,
            )
            results["Unknown Style"] = result

        # Log summary
        total_playlists = len(results)
        total_successful = sum(1 for r in results.values() if r.success)
        total_tracks_processed = sum(r.total_tracks for r in results.values())
        total_tracks_added = sum(r.added_tracks for r in results.values())

        logger.info(
            f"Style-based playlist creation complete: "
            f"{total_successful}/{total_playlists} playlists created successfully, "
            f"{total_tracks_added}/{total_tracks_processed} tracks added"
        )

        return results

    def _get_track_key(self, track: Track) -> str:
        """Generate a unique key for track caching."""
        artist_name = track.primary_artist.name if track.primary_artist else "Unknown"
        return f"{track.title}|{artist_name}|{track.album.title if track.album else ''}"

    def _get_all_playlists(self) -> List[Any]:
        """Get all user playlists from Tidal."""
        try:
            playlists = self.session.user.playlists()  # type: ignore[union-attr]
            return list(playlists) if playlists else []
        except Exception as e:
            logger.error(f"Error fetching playlists: {e}")
            return []

    def _create_or_get_cached_playlist(
        self, name: str, playlist_cache: Dict[str, Any]
    ) -> Any:
        """
        Create a new playlist or get existing one using cached playlist data.

        Args:
            name: Playlist name
            playlist_cache: Dictionary of existing playlists by name

        Returns:
            Tidal playlist object
        """
        # Check cache first
        if name in playlist_cache:
            logger.info(f"Found existing playlist: {name}")
            return playlist_cache[name]

        # Create new playlist
        logger.info(f"Creating new playlist: {name}")
        try:
            description = "Imported from Discogs"
            playlist = self.session.user.create_playlist(  # type: ignore[union-attr]
                name, description
            )
            # Add to cache for future lookups
            playlist_cache[name] = playlist
            return playlist  # type: ignore[no-any-return]
        except Exception as e:
            raise SyncError(f"Failed to create playlist '{name}': {e}")

    def _add_cached_tracks_to_playlist_direct(
        self,
        playlist: Any,
        playlist_name: str,
        tracks: List[Track],
        tidal_tracks: List[Any],
    ) -> SyncResult:
        """
        Add pre-searched Tidal tracks to an existing playlist object.

        Args:
            playlist: Tidal playlist object
            playlist_name: Name of the playlist for logging
            tracks: Original Track objects for reporting
            tidal_tracks: Pre-searched Tidal track objects

        Returns:
            Sync result with statistics
        """
        if not tracks:
            logger.warning("No tracks provided")
            return SyncResult(
                success=True,
                total_tracks=0,
                matched_tracks=0,
                failed_tracks=0,
                playlist_name=playlist_name,
            )

        logger.info(
            f"Adding {len(tidal_tracks)} found tracks to playlist '{playlist_name}'..."
        )

        added_count = 0
        failed_count = len(tracks) - len(tidal_tracks)  # Tracks not found on Tidal

        # Add all found tracks at once if possible, or one by one
        try:
            if tidal_tracks:
                tidal_track_ids = [track.id for track in tidal_tracks]
                playlist.add(tidal_track_ids)  # type: ignore[attr-defined]
                added_count = len(tidal_tracks)
                logger.info(f"    ✅ Added {added_count} tracks to playlist in batch")
            else:
                logger.info("    ⚠️ No tracks found on Tidal to add")
        except Exception as e:
            # Fallback to individual track addition if batch fails
            logger.warning(f"Batch add failed, trying individual adds: {e}")
            added_count = 0

            for i, tidal_track in enumerate(tidal_tracks, 1):
                try:
                    playlist.add([tidal_track.id])  # type: ignore[attr-defined]
                    added_count += 1
                    logger.debug(f"    ✅ Added track {i}/{len(tidal_tracks)}")
                except Exception as track_error:
                    logger.error(f"    ❌ Failed to add track {i}: {track_error}")
                    failed_count += 1

        result = SyncResult(
            success=added_count > 0,
            total_tracks=len(tracks),
            matched_tracks=len(tidal_tracks),
            failed_tracks=failed_count,
            playlist_name=playlist_name,
        )

        logger.info(
            f"Finished adding tracks to playlist. "
            f"Total: {result.total_tracks}, "
            f"Found: {result.found_tracks}, "
            f"Added: {result.added_tracks}, "
            f"Failed: {result.failed_tracks}"
        )

        return result

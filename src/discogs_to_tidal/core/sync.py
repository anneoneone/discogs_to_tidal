"""
Core synchronization service with album-based optimization.
"""
import logging
from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple

from ..integrations.discogs.client import DiscogsService
from ..integrations.tidal.auth import TidalAuth
from ..integrations.tidal.search import TidalSearchService
from .exceptions import AuthenticationError, SyncError
from .models import Album, SyncResult, Track

logger = logging.getLogger(__name__)


class SyncService:
    """Enhanced synchronization service between Discogs and Tidal."""

    def __init__(
        self,
        discogs_service: DiscogsService,
        tidal_auth: TidalAuth,
        output_dir: Optional[Path] = None,
    ):
        self.discogs_service = discogs_service
        self.tidal_auth = tidal_auth
        self.output_dir = output_dir or Path.cwd() / "output"
        self.search_service: Optional[TidalSearchService] = None

    def sync_collection(
        self,
        progress_callback: Optional[Callable[[str], None]] = None,
        playlist_name: str = "Discogs Collection",
        folder_id: int = 0,
    ) -> SyncResult:
        """
        Synchronize Discogs collection to Tidal using album-based optimization.

        Args:
            progress_callback: Optional callback for progress updates
            playlist_name: Name for the Tidal playlist
            folder_id: Discogs collection folder ID (0 = default "All" folder)

        Returns:
            SyncResult with sync statistics
        """
        try:
            # Initialize Tidal session
            session = self._initialize_tidal_session(progress_callback)

            # Fetch albums from Discogs
            albums_with_tracks = self._fetch_discogs_albums(
                folder_id, progress_callback
            )

            if not albums_with_tracks:
                return self._create_empty_sync_result(playlist_name)

            # Process albums and find matching tracks
            sync_stats = self._process_albums(albums_with_tracks, progress_callback)

            # Create playlist if we found tracks
            playlist_id = None
            if sync_stats["all_found_tracks"]:
                playlist_id = self._handle_playlist_creation(
                    session,
                    playlist_name,
                    sync_stats["all_found_tracks"],
                    progress_callback,
                )
            
            # Create final result
            result = self._create_sync_result(sync_stats, playlist_name, playlist_id)

            self._report_completion(result, len(albums_with_tracks), progress_callback)

            return result

        except Exception as e:
            logger.error(f"Sync failed: {e}")
            return SyncResult(
                success=False,
                total_tracks=0,
                matched_tracks=0,
                failed_tracks=0,
                playlist_name=playlist_name,
                errors=[str(e)],
            )

    def _initialize_tidal_session(
        self, progress_callback: Optional[Callable[[str], None]] = None
    ) -> Any:
        """Initialize Tidal session and search service."""
        if progress_callback:
            progress_callback("Authenticating with Tidal...")

        session = self.tidal_auth.session
        if not session:
            raise AuthenticationError("Failed to authenticate with Tidal")

        self.search_service = TidalSearchService(session)
        return session

    def _fetch_discogs_albums(
        self, folder_id: int, progress_callback: Optional[Callable[[str], None]] = None
    ) -> List[Tuple[Album, List[Track]]]:
        """Fetch albums from Discogs collection."""
        if progress_callback:
            if folder_id == 0:
                progress_callback("Fetching Discogs collection (All folders)...")
            else:
                progress_callback(
                    f"Fetching Discogs collection (Folder ID: {folder_id})..."
                )

        albums_with_tracks = self.discogs_service.get_collection_albums(
            folder_id, progress_callback
        )

        if albums_with_tracks:
            logger.info(f"Processing {len(albums_with_tracks)} albums from Discogs")

        return albums_with_tracks

    def _create_empty_sync_result(self, playlist_name: str) -> SyncResult:
        """Create a SyncResult for when no albums are found."""
        logger.warning("No albums found in Discogs collection")
        return SyncResult(
            success=True,
            total_tracks=0,
            matched_tracks=0,
            failed_tracks=0,
            playlist_name=playlist_name,
        )

    def _setup_output_file(self) -> Path:
        """Setup and prepare the output file for conversion logging."""
        output_file = self.output_dir / "discogs_to_tidal_conversion.json"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Clear previous conversion data
        if output_file.exists():
            output_file.unlink()

        return output_file

    def _process_albums(
        self,
        albums_with_tracks: List[Tuple[Album, List[Track]]],
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> dict:
        """Process all albums and return sync statistics."""
        output_file = self._setup_output_file()

        all_found_tracks = []
        total_tracks = 0
        found_tracks = 0

        for i, (album, tracks) in enumerate(albums_with_tracks, 1):
            # Update progress
            self._report_album_progress(
                i, len(albums_with_tracks), album, progress_callback
            )

            # Process single album
            album_stats = self._process_single_album(album, tracks, output_file)

            # Update totals
            total_tracks += album_stats["total"]
            found_tracks += album_stats["found"]
            all_found_tracks.extend(album_stats["tracks"])

        return {
            "total_tracks": total_tracks,
            "found_tracks": found_tracks,
            "all_found_tracks": all_found_tracks,
        }

    def _report_album_progress(
        self,
        current: int,
        total: int,
        album: Album,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Report progress for current album being processed."""
        if progress_callback:
            artist_name = (
                album.primary_artist.name if album.primary_artist else "Unknown"
            )
            progress_callback(
                f"Processing album {current}/{total}: "
                f"{album.title} by {artist_name}"
            )

        artist_name = album.primary_artist.name if album.primary_artist else "Unknown"
        logger.info(f"Album {current}/{total}: {album.title} by {artist_name}")

    def _process_single_album(
        self, album: Album, tracks: List[Track], output_file: Path
    ) -> dict:
        """Process a single album and return its statistics."""
        logger.info(f"Processing: {album.title} ({len(tracks)} tracks)")

        # Search for this album's tracks on Tidal
        if self.search_service is None:
            raise SyncError("Search service not initialized")

        track_results = self.search_service.find_tracks_by_album(
            album, tracks, output_file
        )

        # Collect results
        found_tracks = []
        total_tracks = 0

        for discogs_track, tidal_track in track_results:
            total_tracks += 1
            if tidal_track:
                found_tracks.append(tidal_track)
                logger.debug(f"    ✓ Found: {discogs_track.title}")
            else:
                logger.debug(f"    ✗ Missing: {discogs_track.title}")

        return {
            "total": total_tracks,
            "found": len(found_tracks),
            "tracks": found_tracks,
        }

    def _handle_playlist_creation(
        self,
        session: Any,
        playlist_name: str,
        tracks: List[Any],
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> Optional[str]:
        """Handle playlist creation or update."""
        if progress_callback:
            progress_callback(f"Creating Tidal playlist: {playlist_name}")

        try:
            playlist_id = self._create_or_update_playlist(
                session, playlist_name, tracks
            )
            logger.info(
                f"Created/updated playlist '{playlist_name}' with "
                f"{len(tracks)} tracks (ID: {playlist_id})"
            )
            return playlist_id
        except Exception as e:
            logger.error(f"Failed to create playlist: {e}")
            raise SyncError(f"Playlist creation failed: {e}")

    def _create_sync_result(
        self, stats: dict, playlist_name: str, playlist_id: Optional[str] = None
    ) -> SyncResult:
        """Create the final SyncResult object."""
        result = SyncResult(
            success=True,
            total_tracks=stats["total_tracks"],
            matched_tracks=stats["found_tracks"],
            failed_tracks=stats["total_tracks"] - stats["found_tracks"],
            playlist_name=playlist_name,
        )

        # Store playlist_id if available (for potential future use)
        if hasattr(result, "playlist_id") and playlist_id:
            result.playlist_id = playlist_id

        return result

    def _report_completion(
        self,
        result: SyncResult,
        album_count: int,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Report completion of sync operation."""
        if progress_callback:
            progress_callback(
                f"Sync complete! Found {result.matched_tracks}/"
                f"{result.total_tracks} tracks across {album_count} albums"
            )

    def _create_or_update_playlist(
        self, session: Any, playlist_name: str, tracks: List[Any]
    ) -> str:
        """Create or update a Tidal playlist with the found tracks."""
        existing_playlist = self._find_existing_playlist(session, playlist_name)
        track_ids = [track.id for track in tracks]

        if existing_playlist:
            return self._update_existing_playlist(existing_playlist, track_ids)
        else:
            return self._create_new_playlist(session, playlist_name, track_ids)

    def _find_existing_playlist(
        self, session: Any, playlist_name: str
    ) -> Optional[Any]:
        """Find an existing playlist by name."""
        try:
            existing_playlists = session.user.playlists()
            for playlist in existing_playlists:
                if playlist.name == playlist_name:
                    return playlist
        except Exception as e:
            logger.warning(f"Failed to fetch existing playlists: {e}")

        return None

    def _update_existing_playlist(self, playlist: Any, track_ids: List[str]) -> str:
        """Update an existing playlist with new tracks."""
        logger.info(f"Updating existing playlist: {playlist.name}")

        # Clear existing tracks
        self._clear_playlist_tracks(playlist)

        # Add new tracks
        self._add_tracks_to_playlist(playlist, track_ids, "existing")

        return playlist.id  # type: ignore[no-any-return]

    def _create_new_playlist(
        self, session: Any, playlist_name: str, track_ids: List[str]
    ) -> str:
        """Create a new playlist and add tracks."""
        logger.info(f"Creating new playlist: {playlist_name}")

        new_playlist = session.user.create_playlist(
            playlist_name, "Created by discogs-to-tidal"
        )

        # Add tracks
        self._add_tracks_to_playlist(new_playlist, track_ids, "new")

        return new_playlist.id  # type: ignore[no-any-return]

    def _clear_playlist_tracks(self, playlist: Any) -> None:
        """Clear all tracks from an existing playlist."""
        try:
            existing_tracks = playlist.tracks()
            if existing_tracks:
                existing_track_ids = [track.id for track in existing_tracks]
                playlist.remove(existing_track_ids)
                logger.debug(f"Cleared {len(existing_track_ids)} existing tracks")
        except Exception as e:
            logger.warning(f"Failed to clear existing playlist: {e}")

    def _add_tracks_to_playlist(
        self, playlist: Any, track_ids: List[str], playlist_type: str
    ) -> None:
        """Add tracks to a playlist."""
        try:
            playlist.add(track_ids)
            logger.info(f"Added {len(track_ids)} tracks to {playlist_type} playlist")
        except Exception as e:
            error_msg = f"Failed to add tracks to {playlist_type} playlist: {e}"
            logger.error(error_msg)
            raise SyncError(error_msg)

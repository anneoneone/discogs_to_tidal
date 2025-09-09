"""
Discogs API client for fetching collection data.
"""
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, cast

from discogs_client import Client as DiscogsClient  # type: ignore[import-untyped]

from ...core.config import Config
from ...core.exceptions import AuthenticationError, SearchError
from ...core.models import Album, Artist, Track
from .auth import DiscogsAuth, DiscogsAuthStatus

logger = logging.getLogger(__name__)


class DiscogsService:
    """Service for interacting with the Discogs API with improved authentication."""

    def __init__(self, config: Config):
        self.config = config
        self._auth = DiscogsAuth(config)
        self._client: Optional[DiscogsClient] = None
        self._user: Any = None  # Discogs user object
        self._cache_file = Path("output") / "discogs_cache.json"

    @property
    def client(self) -> DiscogsClient:
        """Get authenticated Discogs client."""
        if self._client is None:
            self._client = self._auth.authenticate()
        return self._client

    @property
    def user(self) -> Any:
        """Get authenticated user info."""
        if self._user is None:
            self._user = self._auth.user
        return self._user

    def authenticate(self) -> None:
        """Authenticate with Discogs using the refactored auth system."""
        try:
            self._client = self._auth.authenticate()
            self._user = self._auth.user
            if self._user is not None and hasattr(self._user, "username"):
                logger.info(f"Authenticated as Discogs user: {self._user.username}")
        except Exception as e:
            raise AuthenticationError(f"Discogs authentication failed: {e}")

    def authenticate_with_progress(
        self, progress_callback: Callable[[str, int], None]
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

    def get_collection_tracks(
        self,
        folder_id: int = 0,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> List[Track]:
        """
        Get all tracks from user's Discogs collection.

        Args:
            folder_id: Collection folder ID (0 = default "All" folder)
            progress_callback: Optional callback for real-time progress updates

        Returns:
            List of Track objects
        """
        if self._user is None:
            self.authenticate()

        # After authentication, check if user is properly set
        if self._user is None:
            raise AuthenticationError("Failed to authenticate user")

        logger.info(f"Fetching tracks from collection folder {folder_id}")
        tracks: List[Track] = []

        try:
            # Find the folder with the matching ID
            folder = None
            for f in self._user.collection_folders:
                if f.id == folder_id:
                    folder = f
                    break

            if folder is None:
                available_folders = [
                    f"ID {f.id}: {f.name}" for f in self._user.collection_folders
                ]
                raise SearchError(
                    f"Invalid folder ID {folder_id}. Available folders: "
                    f"{', '.join(available_folders)}"
                )

            releases = list(folder.releases)

            logger.info(f"Found {len(releases)} releases in collection")

            for i, release in enumerate(releases, 1):
                if self.config.max_tracks > 0 and len(tracks) >= self.config.max_tracks:
                    logger.info(f"Reached max_tracks limit ({self.config.max_tracks})")
                    break

                try:
                    # Show real-time progress for each release
                    if progress_callback:
                        release_title = release.release.title
                        progress_callback(
                            f"Fetching release {i}/{len(releases)}: {release_title}"
                        )

                    release_tracks = self._process_release(
                        release.release, i, len(releases)
                    )
                    tracks.extend(release_tracks)

                    # Rate limiting - increase delay after errors
                    time.sleep(0.5)

                except Exception as e:
                    logger.warning(f"Failed to process release {i}: {e}")
                    continue

            logger.info(f"Total tracks fetched: {len(tracks)}")

            # Save tracks metadata to JSON file
            self._save_tracks_to_json(tracks, folder_id)

            return tracks

        except Exception as e:
            raise SearchError(f"Failed to fetch collection: {e}")

    def get_collection_albums(
        self,
        folder_id: int = 0,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> List[tuple]:
        """
        Get all albums from user's Discogs collection with their tracks.

        This is optimized for album-by-album processing.

        Args:
            folder_id: Collection folder ID (0 = default "All" folder)
            progress_callback: Optional callback for real-time progress updates

        Returns:
            List of (Album, List[Track]) tuples
        """
        if self._user is None:
            self.authenticate()

        # After authentication, check if user is properly set
        if self._user is None:
            raise AuthenticationError("Failed to authenticate user")

        logger.info(f"Fetching albums from collection folder {folder_id}")
        albums_with_tracks: List[Tuple[Album, List[Track]]] = []

        try:
            # Load cache
            cache = self._load_cache()
            cache_hits = 0
            cache_misses = 0

            # Find the folder by its ID rather than using array indexing
            target_folder = None

            for folder in self._user.collection_folders:
                if folder.id == folder_id:
                    target_folder = folder
                    break

            if target_folder is None:
                available_folders = [
                    f"ID {folder.id}: {folder.name} ({folder.count} items)"
                    for folder in self._user.collection_folders
                ]
                raise SearchError(
                    f"Folder with ID {folder_id} not found. Available folders: "
                    f"{', '.join(available_folders)}"
                )

            releases = list(target_folder.releases)

            logger.info(f"Found {len(releases)} releases in collection")

            for i, release in enumerate(releases, 1):
                try:
                    # Show real-time progress for each release
                    if progress_callback:
                        release_title = release.release.title
                        progress_callback(
                            f"Fetching release {i}/{len(releases)}: {release_title}"
                        )

                    # Check if release is cached
                    release_id = release.release.id
                    if self._is_release_cached(release_id, cache):
                        cached_result = self._get_cached_release(release_id, cache)
                        if cached_result:
                            album, tracks = cached_result
                            albums_with_tracks.append((album, tracks))
                            cache_hits += 1
                            logger.debug(
                                f"Cache hit for release {release_id}: {album.title}"
                            )
                            continue

                    # Process release if not cached
                    result = self._process_release_to_album(
                        release.release, i, len(releases)
                    )
                    if result[0] is not None and result[1]:
                        album, tracks = result[0], result[1]
                        albums_with_tracks.append((album, tracks))
                        # Cache the processed release
                        self._cache_release(release_id, album, tracks, cache)
                        cache_misses += 1

                    # Rate limiting - increase delay after errors
                    time.sleep(0.5)

                except Exception as e:
                    logger.warning(f"Failed to process release {i}: {e}")
                    continue

            # Save updated cache
            self._save_cache(cache)

            logger.info(f"Total albums fetched: {len(albums_with_tracks)}")
            logger.info(f"Cache performance: {cache_hits} hits, {cache_misses} misses")

            # Save albums metadata to JSON file
            self._save_albums_to_json(albums_with_tracks, folder_id)

            return albums_with_tracks

        except Exception as e:
            raise SearchError(f"Failed to fetch collection: {e}")

    def get_collection_folders(self) -> List[Dict[str, Any]]:
        """
        Get all collection folders for the authenticated user.

        Returns:
            List of folder dictionaries with id, name, and count
        """
        if self._user is None:
            self.authenticate()

        # After authentication, check if user is properly set
        if self._user is None:
            raise AuthenticationError("Failed to authenticate user")

        logger.info("Fetching collection folders")
        folders: List[Dict[str, Any]] = []

        try:
            for folder in self._user.collection_folders:
                folder_info = {
                    "id": folder.id,
                    "name": folder.name,
                    "count": folder.count,
                }
                folders.append(folder_info)
                logger.debug(
                    f"Found folder: {folder.name} "
                    f"(ID: {folder.id}, Count: {folder.count})"
                )

            return folders

        except Exception as e:
            raise SearchError(f"Failed to fetch collection folders: {e}")

    def _load_cache(self) -> Dict[str, Any]:
        """Load cached release data."""
        if not self._cache_file.exists():
            return {}

        try:
            with open(self._cache_file, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
                return cast(Dict[str, Any], cache_data)
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")
            return {}

    def _save_cache(self, cache_data: Dict[str, Any]) -> None:
        """Save cache data to file."""
        try:
            # Ensure output directory exists
            self._cache_file.parent.mkdir(parents=True, exist_ok=True)

            with open(self._cache_file, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            logger.debug(
                f"Cache saved with {len(cache_data.get('releases', {}))} releases"
            )
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")

    def _is_release_cached(self, release_id: int, cache: Dict[str, Any]) -> bool:
        """Check if a release is already cached."""
        releases_cache = cache.get("releases", {})
        return str(release_id) in releases_cache

    def _get_cached_release(
        self, release_id: int, cache: Dict[str, Any]
    ) -> Optional[Tuple[Album, List[Track]]]:
        """Get cached release data."""
        releases_cache = cache.get("releases", {})
        cached_data = releases_cache.get(str(release_id))

        if not cached_data:
            return None

        try:
            # Reconstruct Album object from cached data
            album_data = cached_data["album"]

            # Reconstruct artists
            artists = []
            for artist_data in album_data.get("artists", []):
                artists.append(Artist(id=artist_data["id"], name=artist_data["name"]))

            # Reconstruct Album (primary_artist is a computed property)
            album = Album(
                id=album_data["id"],
                title=album_data["title"],
                artists=artists,
                year=album_data.get("year"),
                genres=album_data.get("genres", []),
                styles=album_data.get("styles", []),
            )

            # Reconstruct tracks
            tracks = []
            for track_data in cached_data.get("tracks", []):
                # Reconstruct track artists
                track_artists = []
                for artist_data in track_data.get("artists", []):
                    track_artists.append(
                        Artist(id=artist_data["id"], name=artist_data["name"])
                    )

                # Create track without primary_artist (it's a computed property)
                track = Track(
                    title=track_data["title"],
                    artists=track_artists,
                    track_number=track_data.get("track_number"),
                    duration=track_data.get("duration"),
                    id=track_data.get("id"),
                )
                tracks.append(track)

            logger.debug(f"Loaded cached release: {album.title} ({len(tracks)} tracks)")
            return album, tracks

        except Exception as e:
            logger.warning(f"Failed to reconstruct cached release {release_id}: {e}")
            return None

    def _cache_release(
        self, release_id: int, album: Album, tracks: List[Track], cache: Dict[str, Any]
    ) -> None:
        """Cache a processed release."""
        if "releases" not in cache:
            cache["releases"] = {}

        # Convert to serializable format
        album_data = {
            "id": album.id,
            "title": album.title,
            "year": album.year,
            "genres": album.genres,
            "styles": album.styles,
            "is_ep": album.is_ep,
            "artists": [
                {"id": artist.id, "name": artist.name} for artist in album.artists
            ],
            "primary_artist": {
                "id": album.primary_artist.id,
                "name": album.primary_artist.name,
            }
            if album.primary_artist
            else None,
        }

        tracks_data = []
        for track in tracks:
            track_data = {
                "title": track.title,
                "track_number": track.track_number,
                "duration": track.duration,
                "duration_formatted": track.duration_formatted,
                "artists": [
                    {"id": artist.id, "name": artist.name} for artist in track.artists
                ],
                "primary_artist": {
                    "id": track.primary_artist.id,
                    "name": track.primary_artist.name,
                }
                if track.primary_artist
                else None,
            }
            tracks_data.append(track_data)

        cache["releases"][str(release_id)] = {
            "album": album_data,
            "tracks": tracks_data,
            "cached_at": datetime.now().isoformat(),
        }

    def _process_release_to_album(
        self, release: Any, release_num: int, total_releases: int
    ) -> Tuple[Optional[Album], List[Track]]:
        """Process a single release and return album with tracks."""
        # Reduced logging since we now have real-time progress via callback
        logger.debug(
            f"Processing release {release_num}/{total_releases}: {release.title}"
        )

        try:
            # Safely access release data with retry logic
            release_data = self._safe_get_release_data(release)
            if not release_data:
                logger.warning(f"Failed to get data for release {release_num}")
                return None, []

            # Get release-level artists
            release_artists = self._extract_artists(release_data.get("artists", []))

            # Create album object
            album = Album(
                title=release.title,
                artists=release_artists,
                year=release_data.get("year"),
                id=str(release.id),
                genres=release_data.get("genres", []),
                styles=release_data.get("styles", []),
            )

            # Process each track with safe tracklist access
            tracks = []
            tracklist = self._safe_get_tracklist(release)
            if tracklist:
                for track_data in tracklist:
                    try:
                        track = self._create_track_from_data(
                            track_data.data, album, release_artists
                        )
                        if track:
                            tracks.append(track)

                    except Exception as e:
                        logger.warning(f"Failed to process track: {e}")
                        continue

            return album, tracks

        except Exception as e:
            logger.warning(f"Failed to process release {release_num}: {e}")
            return None, []

    def _process_release(
        self, release: Any, release_num: int, total_releases: int
    ) -> List[Track]:
        """Process a single release and extract tracks."""
        # Reduced logging since we now have real-time progress via callback
        logger.debug(
            f"Processing release {release_num}/{total_releases}: {release.title}"
        )

        tracks = []

        try:
            # Safely access release data with retry logic
            release_data = self._safe_get_release_data(release)
            if not release_data:
                logger.warning(f"Failed to get data for release {release_num}")
                return []

            # Get release-level artists
            release_artists = self._extract_artists(release_data.get("artists", []))

            # Create album object
            album = Album(
                title=release.title,
                artists=release_artists,
                year=release_data.get("year"),
                id=str(release.id),
                genres=release_data.get("genres", []),
                styles=release_data.get("styles", []),
            )

            # Process each track with safe tracklist access
            tracklist = self._safe_get_tracklist(release)
            if tracklist:
                for track_data in tracklist:
                    try:
                        track = self._create_track_from_data(
                            track_data.data, album, release_artists
                        )
                        if track:
                            tracks.append(track)
                            logger.debug(
                                f"  Found track: {track.title} by "
                                f"{track.primary_artist}"
                            )
                    except Exception as e:
                        logger.warning(f"Failed to process track: {e}")
                        continue

        except Exception as e:
            logger.warning(f"Failed to process release {release_num}: {e}")

        return tracks

    def _create_track_from_data(
        self, track_data: Dict[str, Any], album: Album, fallback_artists: List[Artist]
    ) -> Optional[Track]:
        """Create a Track object from Discogs track data."""
        title = track_data.get("title")
        if not title:
            return None

        # Get track-specific artists or fall back to release artists
        track_artists = self._extract_artists(track_data.get("artists", []))
        if not track_artists:
            track_artists = fallback_artists

        # Parse duration (format: "MM:SS")
        duration = None
        duration_str = track_data.get("duration", "")
        if duration_str:
            try:
                if ":" in duration_str:
                    minutes, seconds = duration_str.split(":")
                    duration = int(minutes) * 60 + int(seconds)
            except (ValueError, IndexError):
                pass

        return Track(
            title=title,
            artists=track_artists,
            album=album,
            duration=duration,
            track_number=self._parse_position(track_data.get("position", "")),
            id=track_data.get("id"),
        )

    def _extract_artists(self, artists_data: List[Dict[str, Any]]) -> List[Artist]:
        """Extract Artist objects from Discogs artist data."""
        artists = []
        for artist_data in artists_data:
            name = artist_data.get("name")
            if name:
                artist = Artist(name=name, id=str(artist_data.get("id", "")))
                artists.append(artist)
        return artists

    def _parse_position(self, position_str: str) -> Optional[int]:
        """Parse track position string to track number."""
        if not position_str:
            return None

        try:
            # Handle formats like "A1", "1", "B2", etc.
            # Extract numeric part
            numeric_part = "".join(c for c in position_str if c.isdigit())
            if numeric_part:
                return int(numeric_part)
        except ValueError:
            pass

        return None

    def _safe_get_release_data(
        self, release: Any, max_retries: int = 3
    ) -> Optional[Dict[str, Any]]:
        """Safely get release data with retry logic for API errors."""
        for attempt in range(max_retries):
            try:
                data = release.data
                return cast(Dict[str, Any], data)
            except Exception as e:
                error_msg = str(e).lower()
                if "expecting value" in error_msg or "json" in error_msg:
                    # This is likely a JSON parsing error from bad API response
                    logger.warning(
                        f"JSON parsing error for release {release.id} "
                        f"(attempt {attempt + 1}/{max_retries}): {e}"
                    )
                    if attempt < max_retries - 1:
                        # Wait before retry, with exponential backoff
                        wait_time = (2**attempt) * 0.5
                        logger.debug(f"Waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
                        continue
                else:
                    # Different error, don't retry
                    logger.warning(f"Failed to get release data: {e}")
                    break

        return None

    def _safe_get_tracklist(
        self, release: Any, max_retries: int = 3
    ) -> Optional[List[Any]]:
        """Safely get release tracklist with retry logic for API errors."""
        for attempt in range(max_retries):
            try:
                tracklist = release.tracklist
                return cast(List[Any], tracklist)
            except Exception as e:
                error_msg = str(e).lower()
                if "expecting value" in error_msg or "json" in error_msg:
                    # This is likely a JSON parsing error from bad API response
                    logger.warning(
                        f"JSON parsing error for tracklist of release {release.id} "
                        f"(attempt {attempt + 1}/{max_retries}): {e}"
                    )
                    if attempt < max_retries - 1:
                        # Wait before retry, with exponential backoff
                        wait_time = (2**attempt) * 0.5
                        logger.debug(f"Waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
                        continue
                else:
                    # Different error, don't retry
                    logger.warning(f"Failed to get tracklist: {e}")
                    break

        return None

    def _save_tracks_to_json(self, tracks: List[Track], folder_id: int) -> None:
        """Save tracks metadata to JSON file."""
        try:
            # Create output directory
            output_dir = Path("output")
            output_dir.mkdir(parents=True, exist_ok=True)

            # Prepare metadata
            metadata: Dict[str, Any] = {
                "export_info": {
                    "timestamp": datetime.now().isoformat(),
                    "discogs_to_tidal_version": "0.2.0",
                    "folder_id": folder_id,
                    "total_tracks": len(tracks),
                },
                "tracks": [],
            }

            # Convert tracks to dictionaries
            for track in tracks:
                track_data = {
                    "discogs_info": {
                        "id": track.id,
                        "title": track.title,
                        "track_number": track.track_number,
                        "duration_seconds": track.duration,
                        "duration_formatted": track.duration_formatted,
                    },
                    "artists": [
                        {"id": artist.id, "name": artist.name}
                        for artist in track.artists
                    ],
                    "primary_artist": {
                        "id": track.primary_artist.id if track.primary_artist else None,
                        "name": track.primary_artist.name
                        if track.primary_artist
                        else None,
                    }
                    if track.primary_artist
                    else None,
                    "album": {
                        "title": track.album.title if track.album else None,
                        "year": track.album.year if track.album else None,
                        "genres": track.album.genres if track.album else [],
                        "styles": track.album.styles if track.album else [],
                    },
                }
                metadata["tracks"].append(track_data)

            # Save to file
            filename = f"discogs_tracks_folder_{folder_id}.json"
            filepath = output_dir / filename

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

            logger.info(f"✓ Tracks metadata saved to {filepath}")

        except Exception as e:
            logger.warning(f"Failed to save tracks metadata: {e}")

    def _save_albums_to_json(
        self, albums_with_tracks: List[Tuple[Album, List[Track]]], folder_id: int
    ) -> None:
        """Save albums metadata to JSON file."""
        try:
            # Create output directory
            output_dir = Path("output")
            output_dir.mkdir(parents=True, exist_ok=True)

            # Prepare metadata
            metadata: Dict[str, Any] = {
                "export_info": {
                    "timestamp": datetime.now().isoformat(),
                    "discogs_to_tidal_version": "0.2.0",
                    "folder_id": folder_id,
                    "total_albums": len(albums_with_tracks),
                },
                "albums": [],
            }

            # Convert albums to dictionaries
            for album, tracks in albums_with_tracks:
                album_data = {
                    "discogs_info": {
                        "id": album.id,
                        "title": album.title,
                        "year": album.year,
                        "genres": album.genres,
                        "styles": album.styles,
                    },
                    "artists": [
                        {"id": artist.id, "name": artist.name}
                        for artist in album.artists
                    ],
                    "primary_artist": {
                        "id": album.primary_artist.id if album.primary_artist else None,
                        "name": (
                            album.primary_artist.name if album.primary_artist else None
                        ),
                    }
                    if album.primary_artist
                    else None,
                    "tracks": [
                        {
                            "title": track.title,
                            "track_number": track.track_number,
                            "duration_seconds": track.duration,
                            "duration_formatted": track.duration_formatted,
                            "artists": [
                                {"id": artist.id, "name": artist.name}
                                for artist in track.artists
                            ],
                        }
                        for track in tracks
                    ],
                    "track_count": len(tracks),
                }
                metadata["albums"].append(album_data)

            # Save to file
            filename = f"discogs_albums_folder_{folder_id}.json"
            filepath = output_dir / filename

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

            logger.info(f"✓ Albums metadata saved to {filepath}")

        except Exception as e:
            logger.warning(f"Failed to save albums metadata: {e}")

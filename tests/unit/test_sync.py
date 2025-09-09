"""
Unit tests for core.sync module.
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

# Add src directory to path for direct imports
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

# Mock the integration imports before importing the module
sys.modules["discogs_to_tidal.integrations.discogs.client"] = Mock()
sys.modules["discogs_to_tidal.integrations.tidal.auth"] = Mock()
sys.modules["discogs_to_tidal.integrations.tidal.search"] = Mock()

from discogs_to_tidal.core.exceptions import (  # noqa: E402
    AuthenticationError,
    SyncError,
)

# Import after path modification to avoid import issues
from discogs_to_tidal.core.models import Album, Artist, SyncResult, Track  # noqa: E402


class TestSyncService(unittest.TestCase):
    """Test cases for SyncService class."""

    def setUp(self):
        """Set up test fixtures before each test."""
        # Create test data
        self.test_artist = Artist(name="Test Artist", id="artist123")
        self.test_album = Album(
            title="Test Album", artists=[self.test_artist], year=2023, id="album123"
        )
        self.test_track = Track(
            title="Test Track",
            artists=[self.test_artist],
            album=self.test_album,
            duration=180,
            id="track123",
        )

        # Mock dependencies
        self.mock_discogs_service = Mock()
        self.mock_tidal_auth = Mock()
        self.mock_session = Mock()
        self.mock_tidal_auth.session = self.mock_session

        # Create temp directory for output
        self.temp_dir = tempfile.mkdtemp()
        self.output_dir = Path(self.temp_dir)

    def tearDown(self):
        """Clean up after each test."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_sync_service(self):
        """Helper to create SyncService with mocked dependencies."""
        # Import after sys.path modification and mocking
        from discogs_to_tidal.core.sync import SyncService

        return SyncService(
            discogs_service=self.mock_discogs_service,
            tidal_auth=self.mock_tidal_auth,
            output_dir=self.output_dir,
        )

    def test_sync_service_initialization(self):
        """Test SyncService initialization."""
        sync_service = self._create_sync_service()

        self.assertEqual(sync_service.discogs_service, self.mock_discogs_service)
        self.assertEqual(sync_service.tidal_auth, self.mock_tidal_auth)
        self.assertEqual(sync_service.output_dir, self.output_dir)
        self.assertIsNone(sync_service.search_service)

    def test_sync_service_initialization_default_output_dir(self):
        """Test SyncService initialization with default output directory."""
        from discogs_to_tidal.core.sync import SyncService

        sync_service = SyncService(
            discogs_service=self.mock_discogs_service, tidal_auth=self.mock_tidal_auth
        )

        expected_output_dir = Path.cwd() / "output"
        self.assertEqual(sync_service.output_dir, expected_output_dir)

    def test_initialize_tidal_session_no_callback(self):
        """Test Tidal session initialization without callback."""
        sync_service = self._create_sync_service()

        tidal_search_path = (
            "discogs_to_tidal.integrations.tidal.search.TidalSearchService"
        )
        with patch(tidal_search_path):
            result = sync_service._initialize_tidal_session()

            self.assertEqual(result, self.mock_session)

    def test_initialize_tidal_session_failure(self):
        """Test Tidal session initialization failure."""
        sync_service = self._create_sync_service()
        self.mock_tidal_auth.session = None

        with self.assertRaises(AuthenticationError) as cm:
            sync_service._initialize_tidal_session()

        self.assertIn("Failed to authenticate with Tidal", str(cm.exception))

    def test_fetch_discogs_albums_success(self):
        """Test successful Discogs albums fetching."""
        sync_service = self._create_sync_service()
        mock_albums = [(self.test_album, [self.test_track])]
        self.mock_discogs_service.get_collection_albums.return_value = mock_albums
        mock_callback = Mock()

        result = sync_service._fetch_discogs_albums(0, mock_callback)

        self.assertEqual(result, mock_albums)
        self.mock_discogs_service.get_collection_albums.assert_called_once_with(0)
        mock_callback.assert_called_once_with(
            "Fetching Discogs collection (All folders)..."
        )

    def test_fetch_discogs_albums_specific_folder(self):
        """Test Discogs albums fetching for specific folder."""
        sync_service = self._create_sync_service()
        mock_albums = [(self.test_album, [self.test_track])]
        self.mock_discogs_service.get_collection_albums.return_value = mock_albums
        mock_callback = Mock()

        result = sync_service._fetch_discogs_albums(123, mock_callback)

        self.assertEqual(result, mock_albums)
        mock_callback.assert_called_once_with(
            "Fetching Discogs collection (Folder ID: 123)..."
        )

    def test_create_empty_sync_result(self):
        """Test creation of empty sync result."""
        sync_service = self._create_sync_service()

        result = sync_service._create_empty_sync_result("Test Playlist")

        self.assertIsInstance(result, SyncResult)
        self.assertTrue(result.success)
        self.assertEqual(result.total_tracks, 0)
        self.assertEqual(result.matched_tracks, 0)
        self.assertEqual(result.failed_tracks, 0)
        self.assertEqual(result.playlist_name, "Test Playlist")

    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.unlink")
    def test_setup_output_file(self, mock_unlink, mock_exists, mock_mkdir):
        """Test output file setup."""
        sync_service = self._create_sync_service()
        mock_exists.return_value = True

        result = sync_service._setup_output_file()

        expected_path = self.output_dir / "discogs_to_tidal_conversion.json"
        self.assertEqual(result, expected_path)
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_unlink.assert_called_once()

    def test_report_album_progress(self):
        """Test album progress reporting."""
        sync_service = self._create_sync_service()
        mock_callback = Mock()

        sync_service._report_album_progress(1, 5, self.test_album, mock_callback)

        expected_message = "Processing album 1/5: Test Album by Test Artist"
        mock_callback.assert_called_once_with(expected_message)

    def test_process_single_album(self):
        """Test processing a single album."""
        sync_service = self._create_sync_service()
        sync_service.search_service = Mock()

        # Mock search results
        mock_tidal_track = Mock()
        mock_tidal_track.id = "tidal_track_123"
        track_results = [(self.test_track, mock_tidal_track)]
        sync_service.search_service.find_tracks_by_album.return_value = track_results

        mock_output_file = Mock()

        result = sync_service._process_single_album(
            self.test_album, [self.test_track], mock_output_file
        )

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["found"], 1)
        self.assertEqual(result["tracks"], [mock_tidal_track])

    def test_create_sync_result(self):
        """Test creation of sync result."""
        sync_service = self._create_sync_service()

        stats = {
            "total_tracks": 10,
            "found_tracks": 8,
            "all_found_tracks": [Mock() for _ in range(8)],
        }

        result = sync_service._create_sync_result(
            stats, "Test Playlist", "playlist_123"
        )

        self.assertIsInstance(result, SyncResult)
        self.assertTrue(result.success)
        self.assertEqual(result.total_tracks, 10)
        self.assertEqual(result.matched_tracks, 8)
        self.assertEqual(result.failed_tracks, 2)
        self.assertEqual(result.playlist_name, "Test Playlist")

    def test_find_existing_playlist_found(self):
        """Test finding an existing playlist."""
        sync_service = self._create_sync_service()
        mock_session = Mock()

        # Mock existing playlists
        mock_playlist1 = Mock()
        mock_playlist1.name = "Other Playlist"
        mock_playlist2 = Mock()
        mock_playlist2.name = "Test Playlist"

        mock_session.user.playlists.return_value = [mock_playlist1, mock_playlist2]

        result = sync_service._find_existing_playlist(mock_session, "Test Playlist")

        self.assertEqual(result, mock_playlist2)

    def test_find_existing_playlist_not_found(self):
        """Test finding a non-existing playlist."""
        sync_service = self._create_sync_service()
        mock_session = Mock()

        mock_playlist1 = Mock()
        mock_playlist1.name = "Other Playlist"
        mock_session.user.playlists.return_value = [mock_playlist1]

        result = sync_service._find_existing_playlist(mock_session, "Test Playlist")

        self.assertIsNone(result)

    def test_clear_playlist_tracks_success(self):
        """Test clearing playlist tracks successfully."""
        sync_service = self._create_sync_service()
        mock_playlist = Mock()

        mock_track1 = Mock()
        mock_track1.id = "track1"
        mock_track2 = Mock()
        mock_track2.id = "track2"
        mock_playlist.tracks.return_value = [mock_track1, mock_track2]

        sync_service._clear_playlist_tracks(mock_playlist)

        mock_playlist.remove.assert_called_once_with(["track1", "track2"])

    def test_add_tracks_to_playlist_success(self):
        """Test adding tracks to playlist successfully."""
        sync_service = self._create_sync_service()
        mock_playlist = Mock()
        track_ids = ["track1", "track2", "track3"]

        sync_service._add_tracks_to_playlist(mock_playlist, track_ids, "new")

        mock_playlist.add.assert_called_once_with(track_ids)

    def test_add_tracks_to_playlist_failure(self):
        """Test adding tracks to playlist failure."""
        sync_service = self._create_sync_service()
        mock_playlist = Mock()
        mock_playlist.add.side_effect = Exception("API Error")
        track_ids = ["track1", "track2"]

        with self.assertRaises(SyncError) as cm:
            sync_service._add_tracks_to_playlist(mock_playlist, track_ids, "existing")

        self.assertIn("Failed to add tracks to existing playlist", str(cm.exception))

    def test_create_new_playlist_success(self):
        """Test creating a new playlist successfully."""
        sync_service = self._create_sync_service()
        mock_session = Mock()
        mock_playlist = Mock()
        mock_playlist.id = "new_playlist_123"
        mock_session.user.create_playlist.return_value = mock_playlist

        track_ids = ["track1", "track2"]

        result = sync_service._create_new_playlist(
            mock_session, "Test Playlist", track_ids
        )

        self.assertEqual(result, "new_playlist_123")
        mock_session.user.create_playlist.assert_called_once_with(
            "Test Playlist", "Created by discogs-to-tidal"
        )
        mock_playlist.add.assert_called_once_with(track_ids)

    def test_update_existing_playlist_success(self):
        """Test updating an existing playlist successfully."""
        sync_service = self._create_sync_service()
        mock_playlist = Mock()
        mock_playlist.id = "existing_playlist_123"
        mock_playlist.name = "Test Playlist"
        mock_playlist.tracks.return_value = []  # No existing tracks

        track_ids = ["track1", "track2"]

        result = sync_service._update_existing_playlist(mock_playlist, track_ids)

        self.assertEqual(result, "existing_playlist_123")
        mock_playlist.add.assert_called_once_with(track_ids)

    @patch("discogs_to_tidal.core.sync.SyncService._find_existing_playlist")
    @patch("discogs_to_tidal.core.sync.SyncService._create_new_playlist")
    def test_create_or_update_playlist_new(self, mock_create_new, mock_find_existing):
        """Test creating a new playlist when none exists."""
        sync_service = self._create_sync_service()
        mock_session = Mock()
        mock_tracks = [Mock() for _ in range(3)]
        for i, track in enumerate(mock_tracks):
            track.id = f"track{i+1}"

        mock_find_existing.return_value = None
        mock_create_new.return_value = "new_playlist_123"

        result = sync_service._create_or_update_playlist(
            mock_session, "Test Playlist", mock_tracks
        )

        self.assertEqual(result, "new_playlist_123")
        mock_find_existing.assert_called_once_with(mock_session, "Test Playlist")
        mock_create_new.assert_called_once_with(
            mock_session, "Test Playlist", ["track1", "track2", "track3"]
        )

    @patch("discogs_to_tidal.core.sync.SyncService._find_existing_playlist")
    @patch("discogs_to_tidal.core.sync.SyncService._update_existing_playlist")
    def test_create_or_update_playlist_existing(
        self, mock_update_existing, mock_find_existing
    ):
        """Test updating an existing playlist."""
        sync_service = self._create_sync_service()
        mock_session = Mock()
        mock_tracks = [Mock() for _ in range(2)]
        for i, track in enumerate(mock_tracks):
            track.id = f"track{i+1}"

        mock_playlist = Mock()
        mock_find_existing.return_value = mock_playlist
        mock_update_existing.return_value = "existing_playlist_123"

        result = sync_service._create_or_update_playlist(
            mock_session, "Test Playlist", mock_tracks
        )

        self.assertEqual(result, "existing_playlist_123")
        mock_find_existing.assert_called_once_with(mock_session, "Test Playlist")
        mock_update_existing.assert_called_once_with(
            mock_playlist, ["track1", "track2"]
        )

    @patch("discogs_to_tidal.core.sync.SyncService._initialize_tidal_session")
    @patch("discogs_to_tidal.core.sync.SyncService._fetch_discogs_albums")
    @patch("discogs_to_tidal.core.sync.SyncService._process_albums")
    @patch("discogs_to_tidal.core.sync.SyncService._handle_playlist_creation")
    def test_sync_collection_success_integration(
        self,
        mock_handle_playlist,
        mock_process_albums,
        mock_fetch_albums,
        mock_init_session,
    ):
        """Test successful sync_collection integration."""
        sync_service = self._create_sync_service()

        # Setup mocks
        mock_init_session.return_value = self.mock_session
        mock_fetch_albums.return_value = [(self.test_album, [self.test_track])]
        mock_process_albums.return_value = {
            "total_tracks": 1,
            "found_tracks": 1,
            "all_found_tracks": [Mock()],
        }
        mock_handle_playlist.return_value = "playlist_123"

        # Run sync
        result = sync_service.sync_collection(
            playlist_name="Integration Test", folder_id=0
        )

        # Verify result
        self.assertIsInstance(result, SyncResult)
        self.assertTrue(result.success)
        self.assertEqual(result.total_tracks, 1)
        self.assertEqual(result.matched_tracks, 1)
        self.assertEqual(result.failed_tracks, 0)
        self.assertEqual(result.playlist_name, "Integration Test")

        # Verify method calls
        mock_init_session.assert_called_once()
        mock_fetch_albums.assert_called_once_with(0, None)
        mock_process_albums.assert_called_once()
        mock_handle_playlist.assert_called_once()

    @patch("discogs_to_tidal.core.sync.SyncService._initialize_tidal_session")
    @patch("discogs_to_tidal.core.sync.SyncService._fetch_discogs_albums")
    def test_sync_collection_no_albums(self, mock_fetch_albums, mock_init_session):
        """Test sync_collection when no albums are found."""
        sync_service = self._create_sync_service()

        mock_init_session.return_value = self.mock_session
        mock_fetch_albums.return_value = []

        result = sync_service.sync_collection(playlist_name="Empty Test")

        self.assertIsInstance(result, SyncResult)
        self.assertTrue(result.success)
        self.assertEqual(result.total_tracks, 0)
        self.assertEqual(result.matched_tracks, 0)
        self.assertEqual(result.playlist_name, "Empty Test")

    @patch("discogs_to_tidal.core.sync.SyncService._initialize_tidal_session")
    def test_sync_collection_auth_failure(self, mock_init_session):
        """Test sync_collection with authentication failure."""
        sync_service = self._create_sync_service()

        mock_init_session.side_effect = AuthenticationError("Auth failed")

        result = sync_service.sync_collection(playlist_name="Auth Fail Test")

        self.assertIsInstance(result, SyncResult)
        self.assertFalse(result.success)
        self.assertEqual(result.total_tracks, 0)
        self.assertEqual(result.playlist_name, "Auth Fail Test")
        self.assertEqual(len(result.errors), 1)
        self.assertIn("Auth failed", result.errors[0])


if __name__ == "__main__":
    unittest.main()

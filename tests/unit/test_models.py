"""
Unit tests for core.models module.
"""

import unittest
from datetime import datetime

from discogs_to_tidal.core.models import Album, Artist, Playlist, SyncResult, Track


class TestArtist(unittest.TestCase):
    """Test cases for Artist model."""

    def test_artist_creation_minimal(self):
        """Test Artist creation with minimal required fields."""
        artist = Artist(name="Test Artist")

        self.assertEqual(artist.name, "Test Artist")
        self.assertIsNone(artist.id)

    def test_artist_creation_with_id(self):
        """Test Artist creation with all fields."""
        artist = Artist(name="Test Artist", id="123")

        self.assertEqual(artist.name, "Test Artist")
        self.assertEqual(artist.id, "123")

    def test_artist_str_representation(self):
        """Test Artist string representation."""
        artist = Artist(name="Pink Floyd")

        self.assertEqual(str(artist), "Pink Floyd")

    def test_artist_equality(self):
        """Test Artist equality comparison."""
        artist1 = Artist(name="Test Artist", id="123")
        artist2 = Artist(name="Test Artist", id="123")
        artist3 = Artist(name="Different Artist", id="123")

        self.assertEqual(artist1, artist2)
        self.assertNotEqual(artist1, artist3)


class TestAlbum(unittest.TestCase):
    """Test cases for Album model."""

    def setUp(self):
        """Set up test fixtures."""
        self.artist1 = Artist(name="Artist One", id="1")
        self.artist2 = Artist(name="Artist Two", id="2")

    def test_album_creation_minimal(self):
        """Test Album creation with minimal required fields."""
        album = Album(title="Test Album", artists=[self.artist1])

        self.assertEqual(album.title, "Test Album")
        self.assertEqual(album.artists, [self.artist1])
        self.assertIsNone(album.year)
        self.assertIsNone(album.id)
        self.assertEqual(album.genres, [])  # Should be initialized in __post_init__

    def test_album_creation_full(self):
        """Test Album creation with all fields."""
        album = Album(
            title="Test Album",
            artists=[self.artist1, self.artist2],
            year=2023,
            id="album123",
            genres=["Rock", "Pop"],
        )

        self.assertEqual(album.title, "Test Album")
        self.assertEqual(album.artists, [self.artist1, self.artist2])
        self.assertEqual(album.year, 2023)
        self.assertEqual(album.id, "album123")
        self.assertEqual(album.genres, ["Rock", "Pop"])

    def test_album_post_init_genres(self):
        """Test Album __post_init__ initializes empty genres list."""
        album = Album(title="Test", artists=[self.artist1])

        self.assertEqual(album.genres, [])
        self.assertIsInstance(album.genres, list)

    def test_album_artist_names_property(self):
        """Test Album artist_names property."""
        album = Album(title="Test", artists=[self.artist1, self.artist2])

        expected_names = ["Artist One", "Artist Two"]
        self.assertEqual(album.artist_names, expected_names)

    def test_album_artist_names_empty(self):
        """Test Album artist_names property with empty artists."""
        album = Album(title="Test", artists=[])

        self.assertEqual(album.artist_names, [])

    def test_album_primary_artist_property(self):
        """Test Album primary_artist property."""
        album = Album(title="Test", artists=[self.artist1, self.artist2])

        self.assertEqual(album.primary_artist, self.artist1)

    def test_album_primary_artist_empty(self):
        """Test Album primary_artist property with empty artists."""
        album = Album(title="Test", artists=[])

        self.assertIsNone(album.primary_artist)

    def test_album_is_ep_property(self):
        """Test Album is_ep property."""
        album = Album(title="Test", artists=[self.artist1])

        # Currently always returns True according to implementation
        self.assertTrue(album.is_ep)

    def test_album_str_representation_single_artist(self):
        """Test Album string representation with single artist."""
        album = Album(title="Dark Side of the Moon", artists=[self.artist1])

        expected = "Dark Side of the Moon by Artist One"
        self.assertEqual(str(album), expected)

    def test_album_str_representation_multiple_artists(self):
        """Test Album string representation with multiple artists."""
        album = Album(title="Collaboration", artists=[self.artist1, self.artist2])

        expected = "Collaboration by Artist One & Artist Two"
        self.assertEqual(str(album), expected)

    def test_album_str_representation_no_artists(self):
        """Test Album string representation with no artists."""
        album = Album(title="Unknown Album", artists=[])

        expected = "Unknown Album by "
        self.assertEqual(str(album), expected)


class TestTrack(unittest.TestCase):
    """Test cases for Track model."""

    def setUp(self):
        """Set up test fixtures."""
        self.artist1 = Artist(name="Track Artist", id="1")
        self.artist2 = Artist(name="Featured Artist", id="2")
        self.album = Album(title="Test Album", artists=[self.artist1])

    def test_track_creation_minimal(self):
        """Test Track creation with minimal required fields."""
        track = Track(title="Test Track", artists=[self.artist1])

        self.assertEqual(track.title, "Test Track")
        self.assertEqual(track.artists, [self.artist1])
        self.assertIsNone(track.album)
        self.assertIsNone(track.duration)
        self.assertIsNone(track.track_number)
        self.assertIsNone(track.disc_number)
        self.assertIsNone(track.id)

    def test_track_creation_full(self):
        """Test Track creation with all fields."""
        track = Track(
            title="Test Track",
            artists=[self.artist1, self.artist2],
            album=self.album,
            duration=240,  # 4 minutes
            track_number=3,
            disc_number=1,
            id="track123",
        )

        self.assertEqual(track.title, "Test Track")
        self.assertEqual(track.artists, [self.artist1, self.artist2])
        self.assertEqual(track.album, self.album)
        self.assertEqual(track.duration, 240)
        self.assertEqual(track.track_number, 3)
        self.assertEqual(track.disc_number, 1)
        self.assertEqual(track.id, "track123")

    def test_track_artist_names_property(self):
        """Test Track artist_names property."""
        track = Track(title="Test", artists=[self.artist1, self.artist2])

        expected_names = ["Track Artist", "Featured Artist"]
        self.assertEqual(track.artist_names, expected_names)

    def test_track_artist_names_empty(self):
        """Test Track artist_names property with empty artists."""
        track = Track(title="Test", artists=[])

        self.assertEqual(track.artist_names, [])

    def test_track_primary_artist_property(self):
        """Test Track primary_artist property."""
        track = Track(title="Test", artists=[self.artist1, self.artist2])

        self.assertEqual(track.primary_artist, self.artist1)

    def test_track_primary_artist_empty(self):
        """Test Track primary_artist property with empty artists."""
        track = Track(title="Test", artists=[])

        self.assertIsNone(track.primary_artist)

    def test_track_duration_formatted_with_duration(self):
        """Test Track duration_formatted property with valid duration."""
        track = Track(title="Test", artists=[self.artist1], duration=185)  # 3:05

        self.assertEqual(track.duration_formatted, "3:05")

    def test_track_duration_formatted_with_seconds_padding(self):
        """Test Track duration_formatted property with seconds needing padding."""
        track = Track(title="Test", artists=[self.artist1], duration=123)  # 2:03

        self.assertEqual(track.duration_formatted, "2:03")

    def test_track_duration_formatted_without_duration(self):
        """Test Track duration_formatted property with no duration."""
        track = Track(title="Test", artists=[self.artist1])

        self.assertEqual(track.duration_formatted, "Unknown")

    def test_track_duration_formatted_zero_duration(self):
        """Test Track duration_formatted property with zero duration."""
        track = Track(title="Test", artists=[self.artist1], duration=0)

        self.assertEqual(track.duration_formatted, "0:00")

    def test_track_duration_formatted_long_duration(self):
        """Test Track duration_formatted property with long duration."""
        track = Track(title="Test", artists=[self.artist1], duration=3661)  # 61:01

        self.assertEqual(track.duration_formatted, "61:01")

    def test_track_str_representation_single_artist(self):
        """Test Track string representation with single artist."""
        track = Track(title="Bohemian Rhapsody", artists=[self.artist1])

        expected = "Bohemian Rhapsody by Track Artist"
        self.assertEqual(str(track), expected)

    def test_track_str_representation_multiple_artists(self):
        """Test Track string representation with multiple artists."""
        track = Track(title="Collaboration", artists=[self.artist1, self.artist2])

        expected = "Collaboration by Track Artist & Featured Artist"
        self.assertEqual(str(track), expected)

    def test_track_str_representation_no_artists(self):
        """Test Track string representation with no artists."""
        track = Track(title="Unknown Track", artists=[])

        expected = "Unknown Track by "
        self.assertEqual(str(track), expected)


class TestPlaylist(unittest.TestCase):
    """Test cases for Playlist model."""

    def setUp(self):
        """Set up test fixtures."""
        self.artist = Artist(name="Test Artist")
        self.track1 = Track(title="Track 1", artists=[self.artist], duration=180)
        self.track2 = Track(title="Track 2", artists=[self.artist], duration=240)
        self.track3 = Track(title="Track 3", artists=[self.artist])  # No duration

    def test_playlist_creation_minimal(self):
        """Test Playlist creation with minimal required fields."""
        playlist = Playlist(name="Test Playlist", tracks=[])

        self.assertEqual(playlist.name, "Test Playlist")
        self.assertEqual(playlist.tracks, [])
        self.assertIsNone(playlist.id)
        self.assertIsNone(playlist.description)
        self.assertIsInstance(playlist.created_at, datetime)

    def test_playlist_creation_full(self):
        """Test Playlist creation with all fields."""
        created_time = datetime(2023, 1, 1, 12, 0, 0)
        playlist = Playlist(
            name="Test Playlist",
            tracks=[self.track1, self.track2],
            id="playlist123",
            description="Test description",
            created_at=created_time,
        )

        self.assertEqual(playlist.name, "Test Playlist")
        self.assertEqual(playlist.tracks, [self.track1, self.track2])
        self.assertEqual(playlist.id, "playlist123")
        self.assertEqual(playlist.description, "Test description")
        self.assertEqual(playlist.created_at, created_time)

    def test_playlist_post_init_created_at(self):
        """Test Playlist __post_init__ sets created_at if None."""
        before_creation = datetime.now()
        playlist = Playlist(name="Test", tracks=[])
        after_creation = datetime.now()

        self.assertIsNotNone(playlist.created_at)
        self.assertGreaterEqual(playlist.created_at, before_creation)
        self.assertLessEqual(playlist.created_at, after_creation)

    def test_playlist_track_count_property(self):
        """Test Playlist track_count property."""
        playlist = Playlist(name="Test", tracks=[self.track1, self.track2])

        self.assertEqual(playlist.track_count, 2)

    def test_playlist_track_count_empty(self):
        """Test Playlist track_count property with empty tracks."""
        playlist = Playlist(name="Test", tracks=[])

        self.assertEqual(playlist.track_count, 0)

    def test_playlist_total_duration_property(self):
        """Test Playlist total_duration property."""
        playlist = Playlist(name="Test", tracks=[self.track1, self.track2])

        # track1: 180s, track2: 240s = 420s total
        self.assertEqual(playlist.total_duration, 420)

    def test_playlist_total_duration_with_none_durations(self):
        """Test Playlist total_duration property with None durations."""
        playlist = Playlist(name="Test", tracks=[self.track1, self.track3])

        # track1: 180s, track3: None (treated as 0) = 180s total
        self.assertEqual(playlist.total_duration, 180)

    def test_playlist_total_duration_all_none(self):
        """Test Playlist total_duration property with all None durations."""
        track_no_duration = Track(title="No Duration", artists=[self.artist])
        playlist = Playlist(name="Test", tracks=[track_no_duration, self.track3])

        self.assertEqual(playlist.total_duration, 0)

    def test_playlist_total_duration_formatted_minutes_only(self):
        """Test Playlist total_duration_formatted property under 1 hour."""
        playlist = Playlist(name="Test", tracks=[self.track1, self.track2])

        # 420 seconds = 7:00
        self.assertEqual(playlist.total_duration_formatted, "7:00")

    def test_playlist_total_duration_formatted_with_hours(self):
        """Test Playlist total_duration_formatted property over 1 hour."""
        long_track = Track(title="Long", artists=[self.artist], duration=3600)  # 1 hour
        playlist = Playlist(name="Test", tracks=[long_track, self.track1])

        # 3780 seconds = 1:03:00
        self.assertEqual(playlist.total_duration_formatted, "1:03:00")

    def test_playlist_total_duration_formatted_zero(self):
        """Test Playlist total_duration_formatted property with zero duration."""
        playlist = Playlist(name="Test", tracks=[])

        self.assertEqual(playlist.total_duration_formatted, "0:00")

    def test_playlist_total_duration_formatted_complex(self):
        """Test Playlist total_duration_formatted property with complex time."""
        long_track = Track(
            title="Long", artists=[self.artist], duration=3665
        )  # 1:01:05
        playlist = Playlist(name="Test", tracks=[long_track])

        self.assertEqual(playlist.total_duration_formatted, "1:01:05")

    def test_playlist_add_track(self):
        """Test Playlist add_track method."""
        playlist = Playlist(name="Test", tracks=[self.track1])

        playlist.add_track(self.track2)

        self.assertEqual(len(playlist.tracks), 2)
        self.assertIn(self.track2, playlist.tracks)

    def test_playlist_remove_track_success(self):
        """Test Playlist remove_track method with existing track."""
        playlist = Playlist(name="Test", tracks=[self.track1, self.track2])

        result = playlist.remove_track(self.track1)

        self.assertTrue(result)
        self.assertEqual(len(playlist.tracks), 1)
        self.assertNotIn(self.track1, playlist.tracks)
        self.assertIn(self.track2, playlist.tracks)

    def test_playlist_remove_track_not_found(self):
        """Test Playlist remove_track method with non-existing track."""
        playlist = Playlist(name="Test", tracks=[self.track1])

        result = playlist.remove_track(self.track2)

        self.assertFalse(result)
        self.assertEqual(len(playlist.tracks), 1)
        self.assertIn(self.track1, playlist.tracks)

    def test_playlist_remove_track_empty_playlist(self):
        """Test Playlist remove_track method on empty playlist."""
        playlist = Playlist(name="Test", tracks=[])

        result = playlist.remove_track(self.track1)

        self.assertFalse(result)
        self.assertEqual(len(playlist.tracks), 0)

    def test_playlist_str_representation(self):
        """Test Playlist string representation."""
        playlist = Playlist(name="My Favorites", tracks=[self.track1, self.track2])

        expected = "Playlist 'My Favorites' with 2 tracks"
        self.assertEqual(str(playlist), expected)

    def test_playlist_str_representation_empty(self):
        """Test Playlist string representation with no tracks."""
        playlist = Playlist(name="Empty Playlist", tracks=[])

        expected = "Playlist 'Empty Playlist' with 0 tracks"
        self.assertEqual(str(playlist), expected)


class TestSyncResult(unittest.TestCase):
    """Test cases for SyncResult model."""

    def test_sync_result_creation_minimal(self):
        """Test SyncResult creation with minimal required fields."""
        result = SyncResult(
            success=True,
            total_tracks=10,
            matched_tracks=8,
            failed_tracks=2,
            playlist_name="Test Playlist",
        )

        self.assertTrue(result.success)
        self.assertEqual(result.total_tracks, 10)
        self.assertEqual(result.matched_tracks, 8)
        self.assertEqual(result.failed_tracks, 2)
        self.assertEqual(result.playlist_name, "Test Playlist")
        self.assertEqual(result.errors, [])  # Should be initialized in __post_init__

    def test_sync_result_creation_full(self):
        """Test SyncResult creation with all fields."""
        errors = ["Error 1", "Error 2"]
        result = SyncResult(
            success=False,
            total_tracks=5,
            matched_tracks=3,
            failed_tracks=2,
            playlist_name="Test Playlist",
            errors=errors,
        )

        self.assertFalse(result.success)
        self.assertEqual(result.total_tracks, 5)
        self.assertEqual(result.matched_tracks, 3)
        self.assertEqual(result.failed_tracks, 2)
        self.assertEqual(result.playlist_name, "Test Playlist")
        self.assertEqual(result.errors, errors)

    def test_sync_result_post_init_errors(self):
        """Test SyncResult __post_init__ initializes empty errors list."""
        result = SyncResult(
            success=True,
            total_tracks=5,
            matched_tracks=5,
            failed_tracks=0,
            playlist_name="Test",
        )

        self.assertEqual(result.errors, [])
        self.assertIsInstance(result.errors, list)

    def test_sync_result_found_tracks_property(self):
        """Test SyncResult found_tracks property (alias for matched_tracks)."""
        result = SyncResult(
            success=True,
            total_tracks=10,
            matched_tracks=7,
            failed_tracks=3,
            playlist_name="Test",
        )

        self.assertEqual(result.found_tracks, 7)
        self.assertEqual(result.found_tracks, result.matched_tracks)

    def test_sync_result_added_tracks_property(self):
        """Test SyncResult added_tracks property."""
        result = SyncResult(
            success=True,
            total_tracks=10,
            matched_tracks=8,
            failed_tracks=2,
            playlist_name="Test",
        )

        # Currently returns same as matched_tracks
        self.assertEqual(result.added_tracks, 8)
        self.assertEqual(result.added_tracks, result.matched_tracks)

    def test_sync_result_match_rate_property(self):
        """Test SyncResult match_rate property."""
        result = SyncResult(
            success=True,
            total_tracks=10,
            matched_tracks=8,
            failed_tracks=2,
            playlist_name="Test",
        )

        self.assertEqual(result.match_rate, 80.0)

    def test_sync_result_match_rate_perfect(self):
        """Test SyncResult match_rate property with 100% success."""
        result = SyncResult(
            success=True,
            total_tracks=5,
            matched_tracks=5,
            failed_tracks=0,
            playlist_name="Test",
        )

        self.assertEqual(result.match_rate, 100.0)

    def test_sync_result_match_rate_zero_total(self):
        """Test SyncResult match_rate property with zero total tracks."""
        result = SyncResult(
            success=True,
            total_tracks=0,
            matched_tracks=0,
            failed_tracks=0,
            playlist_name="Test",
        )

        self.assertEqual(result.match_rate, 0.0)

    def test_sync_result_match_rate_zero_matches(self):
        """Test SyncResult match_rate property with zero matches."""
        result = SyncResult(
            success=False,
            total_tracks=10,
            matched_tracks=0,
            failed_tracks=10,
            playlist_name="Test",
        )

        self.assertEqual(result.match_rate, 0.0)

    def test_sync_result_match_rate_partial(self):
        """Test SyncResult match_rate property with partial matches."""
        result = SyncResult(
            success=True,
            total_tracks=3,
            matched_tracks=1,
            failed_tracks=2,
            playlist_name="Test",
        )

        # 1/3 = 33.333...%
        self.assertAlmostEqual(result.match_rate, 33.333333333333336)

    def test_sync_result_str_representation(self):
        """Test SyncResult string representation."""
        result = SyncResult(
            success=True,
            total_tracks=10,
            matched_tracks=8,
            failed_tracks=2,
            playlist_name="My Playlist",
        )

        expected = "Sync Result: 8/10 tracks (80.0%) to playlist 'My Playlist'"
        self.assertEqual(str(result), expected)

    def test_sync_result_str_representation_zero_total(self):
        """Test SyncResult string representation with zero total."""
        result = SyncResult(
            success=True,
            total_tracks=0,
            matched_tracks=0,
            failed_tracks=0,
            playlist_name="Empty",
        )

        expected = "Sync Result: 0/0 tracks (0.0%) to playlist 'Empty'"
        self.assertEqual(str(result), expected)

    def test_sync_result_str_representation_perfect_match(self):
        """Test SyncResult string representation with perfect match."""
        result = SyncResult(
            success=True,
            total_tracks=5,
            matched_tracks=5,
            failed_tracks=0,
            playlist_name="Perfect",
        )

        expected = "Sync Result: 5/5 tracks (100.0%) to playlist 'Perfect'"
        self.assertEqual(str(result), expected)


if __name__ == "__main__":
    unittest.main()

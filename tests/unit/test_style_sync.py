"""
Tests for style-based playlist functionality.
"""
from unittest.mock import Mock

import pytest

from discogs_to_tidal.core.config import Config
from discogs_to_tidal.core.models import Album, Artist, SyncResult, Track
from discogs_to_tidal.integrations.tidal.client import TidalService


@pytest.fixture
def mock_config():
    """Mock configuration."""
    config = Mock(spec=Config)
    # Mock the tokens_dir property to return a proper Path-like object
    config.tokens_dir = Mock()
    config.tokens_dir.mkdir = Mock()
    # Make tokens_dir behave like a Path for os.chmod
    config.tokens_dir.__fspath__ = Mock(return_value="/tmp/mock_tokens")
    return config


@pytest.fixture
def tidal_service(mock_config):
    """TidalService instance with mocked dependencies."""
    service = TidalService(mock_config)
    service._auth = Mock()
    service._session = Mock()
    service.search_service = Mock()
    return service


@pytest.fixture
def sample_tracks():
    """Sample tracks with different styles."""
    # Artist
    artist = Artist(name="Test Artist", id="1")

    # Albums with different styles
    house_album = Album(
        title="House Album",
        artists=[artist],
        year=2020,
        id="1",
        genres=["Electronic"],
        styles=["House", "Deep House"],
    )

    techno_album = Album(
        title="Techno Album",
        artists=[artist],
        year=2021,
        id="2",
        genres=["Electronic"],
        styles=["Techno"],
    )

    no_style_album = Album(
        title="No Style Album",
        artists=[artist],
        year=2022,
        id="3",
        genres=["Electronic"],
        styles=None,
    )

    # Tracks
    tracks = [
        Track(title="House Track 1", artists=[artist], album=house_album),
        Track(title="House Track 2", artists=[artist], album=house_album),
        Track(title="Techno Track 1", artists=[artist], album=techno_album),
        Track(title="No Style Track", artists=[artist], album=no_style_album),
    ]

    return tracks


def test_create_style_based_playlists_groups_tracks_correctly(
    tidal_service, sample_tracks
):
    """Test that tracks are correctly grouped by style with caching optimization."""
    # Mock the search service to return consistent results
    tidal_service.search_service.find_track = Mock(
        return_value=Mock(id="mock_tidal_track_id")
    )

    # Mock playlist caching methods
    tidal_service._get_all_playlists = Mock(return_value=[])
    tidal_service._create_or_get_cached_playlist = Mock(
        return_value=Mock(name="mock_playlist")
    )
    tidal_service._add_cached_tracks_to_playlist_direct = Mock(
        side_effect=lambda playlist, name, tracks, tidal_tracks: SyncResult(
            success=True,
            total_tracks=len(tracks),
            matched_tracks=len(tidal_tracks),
            failed_tracks=len(tracks) - len(tidal_tracks),
            playlist_name=name,
        )
    )

    # Execute
    results = tidal_service.create_style_based_playlists(sample_tracks, "Test Base")

    # Verify results
    assert len(results) == 4  # House, Deep House, Techno, Unknown Style
    assert "House" in results
    assert "Deep House" in results
    assert "Techno" in results
    assert "Unknown Style" in results

    # Verify that playlists were fetched only once
    tidal_service._get_all_playlists.assert_called_once()

    # Verify that search was called only 4 times (once per unique track)
    assert tidal_service.search_service.find_track.call_count == 4

    # Verify that playlist creation was optimized (cached)
    assert tidal_service._create_or_get_cached_playlist.call_count == 4

    # Verify that _add_cached_tracks_to_playlist_direct was called 4 times
    assert tidal_service._add_cached_tracks_to_playlist_direct.call_count == 4


def test_create_style_based_playlists_caching_efficiency():
    """Test that playlist and track search caching works correctly."""
    tidal_service = TidalService(Mock())

    # Mock playlist caching
    tidal_service._get_all_playlists = Mock(return_value=[])
    tidal_service._create_or_get_cached_playlist = Mock(
        return_value=Mock(name="mock_playlist")
    )
    tidal_service._add_cached_tracks_to_playlist_direct = Mock(
        return_value=SyncResult(
            success=True,
            total_tracks=1,
            matched_tracks=1,
            failed_tracks=0,
            playlist_name="Test",
        )
    )

    # Mock search service to track calls
    search_calls = []

    def track_search_calls(track):
        search_calls.append(f"{track.title}|{track.primary_artist.name}")
        return Mock(id=f"tidal_{track.title}")

    tidal_service.search_service = Mock()
    tidal_service.search_service.find_track = Mock(side_effect=track_search_calls)

    # Create album with multiple styles
    artist = Artist(name="Test Artist", id="1")
    multi_style_album = Album(
        title="Multi Style Album",
        artists=[artist],
        year=2020,
        id="1",
        genres=["Electronic"],
        styles=["House", "Techno", "Ambient"],
    )

    track = Track(title="Multi Style Track", artists=[artist], album=multi_style_album)

    results = tidal_service.create_style_based_playlists([track], "Base")

    # Playlists should be fetched only once at the beginning
    tidal_service._get_all_playlists.assert_called_once()

    # Track should be searched only once, despite being in 3 playlists
    assert len(search_calls) == 1
    assert search_calls[0] == "Multi Style Track|Test Artist"

    # But should be added to all three style playlists
    assert len(results) == 3
    assert tidal_service._add_cached_tracks_to_playlist_direct.call_count == 3

    # Each playlist should be created/retrieved using cache
    assert tidal_service._create_or_get_cached_playlist.call_count == 3


def test_create_style_based_playlists_handles_empty_input(tidal_service):
    """Test handling of empty track list."""
    results = tidal_service.create_style_based_playlists([], "Test Base")

    assert results == {}
    # Should not make any API calls for empty input
    tidal_service.search_service.find_track.assert_not_called()


def test_create_style_based_playlists_handles_tracks_without_albums():
    """Test handling of tracks without album information."""
    # Create a properly mocked config
    mock_config = Mock(spec=Config)
    mock_config.tokens_dir = Mock()
    mock_config.tokens_dir.mkdir = Mock()
    mock_config.tokens_dir.__fspath__ = Mock(return_value="/tmp/mock_tokens")

    tidal_service = TidalService(mock_config)

    # Mock all dependencies to avoid real authentication
    tidal_service._auth = Mock()
    tidal_service._session = Mock()
    tidal_service._get_all_playlists = Mock(return_value=[])
    tidal_service._create_or_get_cached_playlist = Mock(return_value=Mock())

    # Mock search service
    tidal_service.search_service = Mock()
    tidal_service.search_service.find_track = Mock(
        return_value=Mock(id="mock_tidal_track")
    )

    # Mock _add_cached_tracks_to_playlist_direct
    tidal_service._add_cached_tracks_to_playlist_direct = Mock(
        return_value=SyncResult(
            success=True,
            total_tracks=1,
            matched_tracks=1,
            failed_tracks=0,
            playlist_name="Test",
        )
    )

    # Track without album
    track = Track(title="Test Track", artists=[Artist(name="Artist", id="1")])

    results = tidal_service.create_style_based_playlists([track], "Base")

    # Should only create "Unknown Style" playlist
    assert len(results) == 1
    assert "Unknown Style" in results

    # Should search for the track once
    tidal_service.search_service.find_track.assert_called_once_with(track)

    # Should call _add_cached_tracks_to_playlist_direct once
    # Note: the playlist parameter is mocked, so we use ANY to match any playlist
    from unittest.mock import ANY

    tidal_service._add_cached_tracks_to_playlist_direct.assert_called_once_with(
        ANY, "Base - Unknown Style", [track], ANY
    )


def test_create_style_based_playlists_duplicate_tracks_in_multiple_playlists():
    """Test tracks with multiple styles appear in multiple playlists with caching."""
    # Create a properly mocked config
    mock_config = Mock(spec=Config)
    mock_config.tokens_dir = Mock()
    mock_config.tokens_dir.mkdir = Mock()
    mock_config.tokens_dir.__fspath__ = Mock(return_value="/tmp/mock_tokens")

    tidal_service = TidalService(mock_config)

    # Mock all dependencies to avoid real authentication
    tidal_service._auth = Mock()
    tidal_service._session = Mock()
    tidal_service._get_all_playlists = Mock(return_value=[])
    tidal_service._create_or_get_cached_playlist = Mock(return_value=Mock())

    # Mock search service to track calls and return consistent results
    search_calls = []

    def track_search_calls(track):
        search_calls.append(f"{track.title}|{track.primary_artist.name}")
        return Mock(id=f"tidal_{track.title.replace(' ', '_')}")

    tidal_service.search_service = Mock()
    tidal_service.search_service.find_track = Mock(side_effect=track_search_calls)

    # Mock _add_cached_tracks_to_playlist_direct to track calls
    call_log = []

    def cached_add_calls(playlist, playlist_name: str, tracks, tidal_tracks):
        call_log.append(
            (playlist_name, len(tracks), [t.title for t in tracks], len(tidal_tracks))
        )
        return SyncResult(
            success=True,
            total_tracks=len(tracks),
            matched_tracks=len(tidal_tracks),
            failed_tracks=0,
            playlist_name=playlist_name,
        )

    tidal_service._add_cached_tracks_to_playlist_direct = Mock(
        side_effect=cached_add_calls
    )

    # Create album with multiple styles
    artist = Artist(name="Test Artist", id="1")
    multi_style_album = Album(
        title="Multi Style Album",
        artists=[artist],
        year=2020,
        id="1",
        genres=["Electronic"],
        styles=["House", "Techno", "Ambient"],
    )

    track = Track(title="Multi Style Track", artists=[artist], album=multi_style_album)

    results = tidal_service.create_style_based_playlists([track], "Base")

    # Track should appear in all three style playlists
    assert len(results) == 3
    assert all(style in results for style in ["House", "Techno", "Ambient"])

    # Track should be searched only once (caching optimization)
    assert len(search_calls) == 1
    assert search_calls[0] == "Multi Style Track|Test Artist"

    # Verify the same track appears in all three playlists with cached Tidal track
    assert len(call_log) == 3
    for playlist_name, track_count, track_titles, tidal_count in call_log:
        assert track_count == 1
        assert tidal_count == 1  # Found on Tidal
        assert track_titles == ["Multi Style Track"]
        assert playlist_name in ["Base - House", "Base - Techno", "Base - Ambient"]

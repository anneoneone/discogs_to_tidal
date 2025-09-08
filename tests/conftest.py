"""
Test configuration and shared fixtures for pytest
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests"""
    temp_path = tempfile.mkdtemp()
    yield Path(temp_path)
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def mock_discogs_client():
    """Mock Discogs client for testing"""
    mock_client = MagicMock()
    mock_user = MagicMock()
    mock_user.username = "test_user"
    mock_user.collection_folders = []
    mock_client.identity.return_value = mock_user
    return mock_client


@pytest.fixture
def mock_tidal_session():
    """Mock Tidal session for testing"""
    session = MagicMock()
    session.check_login.return_value = True
    session.token_type = "Bearer"
    session.access_token = "test_access_token"
    session.refresh_token = "test_refresh_token"
    return session


@pytest.fixture
def sample_track_data():
    """Sample track data for testing"""
    return {
        'title': 'Bohemian Rhapsody',
        'artist': 'Queen',
        'release': {
            'title': 'A Night at the Opera',
            'year': 1975,
            'artists': [{'name': 'Queen'}]
        }
    }


@pytest.fixture
def sample_tracks_list():
    """Sample list of tracks for testing"""
    return [
        {
            'title': 'Bohemian Rhapsody',
            'artist': 'Queen',
            'release': {
                'title': 'A Night at the Opera',
                'year': 1975,
                'artists': [{'name': 'Queen'}]
            }
        },
        {
            'title': 'Stairway to Heaven',
            'artist': 'Led Zeppelin',
            'release': {
                'title': 'Led Zeppelin IV',
                'year': 1971,
                'artists': [{'name': 'Led Zeppelin'}]
            }
        }
    ]

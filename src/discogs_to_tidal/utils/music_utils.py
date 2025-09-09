"""
Music data utilities.
"""
from typing import Any, Optional, Tuple


def extract_track_info(
    track_data: Any,
) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[int]]:
    """
    Extract track information from various track data formats.

    Args:
        track_data: Track data object or dictionary

    Returns:
        Tuple of (title, artist, album, year)
    """
    # Handle different track data formats
    if hasattr(track_data, "title"):
        # Object with attributes
        title = getattr(track_data, "title", None)
        artist = getattr(track_data, "artist", None)
        album = getattr(track_data, "album", None)
        year = getattr(track_data, "year", None)

        # Handle artist as object
        if (
            hasattr(artist, "name")
            and not isinstance(artist, str)
            and artist is not None
        ):
            artist = artist.name

        # Handle album as object
        if hasattr(album, "title") and not isinstance(album, str) and album is not None:
            album = album.title

    elif isinstance(track_data, dict):
        # Dictionary format
        title = track_data.get("title")
        artist = track_data.get("artist")
        album = track_data.get("album")
        year = track_data.get("year")

    else:
        # Unknown format
        return None, None, None, None

    return title, artist, album, year

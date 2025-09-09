"""
Data models for the discogs_to_tidal package.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class Artist:
    """Represents a music artist."""

    name: str
    id: Optional[str] = None

    def __str__(self) -> str:
        return self.name


@dataclass
class Album:
    """Represents a music album/release."""

    title: str
    artists: List[Artist]
    year: Optional[int] = None
    id: Optional[str] = None
    genres: Optional[List[str]] = None
    styles: Optional[List[str]] = None

    def __post_init__(self) -> None:
        if self.genres is None:
            self.genres = []
        if self.styles is None:
            self.styles = []

    @property
    def artist_names(self) -> List[str]:
        """Get list of artist names."""
        return [artist.name for artist in self.artists]

    @property
    def primary_artist(self) -> Optional[Artist]:
        """Get the primary artist (first in list)."""
        return self.artists[0] if self.artists else None

    @property
    def is_ep(self) -> bool:
        """Check if this album is likely an EP (6 tracks or fewer)."""
        return True  # For now, we'll consider any release as a potential EP candidate

    def __str__(self) -> str:
        artists_str = " & ".join(self.artist_names)
        return f"{self.title} by {artists_str}"


@dataclass
class Track:
    """Represents a music track."""

    title: str
    artists: List[Artist]
    album: Optional[Album] = None
    duration: Optional[int] = None  # Duration in seconds
    track_number: Optional[int] = None
    disc_number: Optional[int] = None
    id: Optional[str] = None

    @property
    def artist_names(self) -> List[str]:
        """Get list of artist names."""
        return [artist.name for artist in self.artists]

    @property
    def primary_artist(self) -> Optional[Artist]:
        """Get the primary artist (first in list)."""
        return self.artists[0] if self.artists else None

    @property
    def duration_formatted(self) -> str:
        """Get duration in MM:SS format."""
        if self.duration is None:
            return "Unknown"
        minutes = self.duration // 60
        seconds = self.duration % 60
        return f"{minutes}:{seconds:02d}"

    def __str__(self) -> str:
        artists_str = " & ".join(self.artist_names)
        return f"{self.title} by {artists_str}"


@dataclass
class Playlist:
    """Represents a music playlist."""

    name: str
    tracks: List[Track]
    id: Optional[str] = None
    description: Optional[str] = None
    created_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = datetime.now()

    @property
    def track_count(self) -> int:
        """Get number of tracks in playlist."""
        return len(self.tracks)

    @property
    def total_duration(self) -> int:
        """Get total duration of all tracks in seconds."""
        return sum(track.duration or 0 for track in self.tracks)

    @property
    def total_duration_formatted(self) -> str:
        """Get total duration in HH:MM:SS format."""
        total = self.total_duration
        hours = total // 3600
        minutes = (total % 3600) // 60
        seconds = total % 60

        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes}:{seconds:02d}"

    def add_track(self, track: Track) -> None:
        """Add a track to the playlist."""
        self.tracks.append(track)

    def remove_track(self, track: Track) -> bool:
        """Remove a track from the playlist. Returns True if removed."""
        try:
            self.tracks.remove(track)
            return True
        except ValueError:
            return False

    def __str__(self) -> str:
        return f"Playlist '{self.name}' with {self.track_count} tracks"


@dataclass
class SyncResult:
    """Represents the result of a synchronization operation."""

    success: bool
    total_tracks: int
    matched_tracks: int
    failed_tracks: int
    playlist_name: str
    errors: Optional[List[str]] = None

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []

    @property
    def found_tracks(self) -> int:
        """Alias for matched_tracks for backward compatibility."""
        return self.matched_tracks

    @property
    def added_tracks(self) -> int:
        """Tracks that were successfully added to playlist."""
        return self.matched_tracks  # For now, all found tracks are added

    @property
    def match_rate(self) -> float:
        """Get the success rate as a percentage."""
        if self.total_tracks == 0:
            return 0.0
        return (self.matched_tracks / self.total_tracks) * 100

    def __str__(self) -> str:
        return (
            f"Sync Result: {self.matched_tracks}/{self.total_tracks} tracks "
            f"({self.match_rate:.1f}%) to playlist '{self.playlist_name}'"
        )

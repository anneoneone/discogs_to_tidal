"""
Enhanced Tidal search functionality with album-based optimization.
"""
import difflib
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import tidalapi

from ...core.models import Album, Track
from ...utils.string_utils import normalize_string

logger = logging.getLogger(__name__)


class TidalSearchService:
    """Enhanced service for searching tracks on Tidal with album optimization."""

    def __init__(self, session: tidalapi.Session):
        self.session = session
        self.album_cache: Dict[str, List[tidalapi.Track]] = {}

    def find_tracks_by_album(
        self, album: Album, tracks: List[Track], output_file: Optional[Path] = None
    ) -> List[Tuple[Track, Optional[tidalapi.Track]]]:
        """
        Find tracks using individual track search with enhanced fuzzy matching.

        This method searches for each track individually with improved
        artist and title cleaning for better matching.

        Args:
            album: Album object from Discogs
            tracks: List of tracks in this album
            output_file: Optional file to write conversion results

        Returns:
            List of tuples (discogs_track, tidal_track_or_none)
        """
        if not tracks:
            return []

        logger.info(
            f"Searching tracks from album: {album.title} by {album.primary_artist}"
        )

        results = []
        conversion_data = {
            "album": {
                "title": album.title,
                "artists": [artist.name for artist in album.artists],
                "year": album.year,
                "discogs_id": album.id,
            },
            "tracks": [],
        }

        # Search for each track individually with enhanced matching
        for i, track in enumerate(tracks, 1):
            artist_name = (
                track.primary_artist.name if track.primary_artist else "Unknown"
            )
            logger.info(
                f"  Track {i}/{len(tracks)}: '{track.title}' by '{artist_name}'"
            )

            tidal_match = self.find_track(track)
            results.append((track, tidal_match))

            # Add to conversion data
            track_data = self._create_track_conversion_data(track, tidal_match)
            conversion_data["tracks"].append(track_data)

            if tidal_match:
                logger.info(
                    f"    ✓ FOUND: '{tidal_match.name}' by '{tidal_match.artist.name}' "
                    f"(ID: {tidal_match.id})"
                )
            else:
                logger.info("    ✗ NOT FOUND: No match on Tidal")

        # EP Optimization: If more than half the tracks were found, try to get complete
        # album/EP
        found_count = sum(1 for _, tidal_track in results if tidal_track is not None)
        if found_count > len(tracks) / 2 and album.is_ep:
            logger.info(
                f"🔍 EP OPTIMIZATION: Found {found_count}/{len(tracks)} tracks, "
                f"attempting to find complete album/EP..."
            )

            # Try to find the complete album on Tidal
            tidal_album_tracks = self._find_album_tracks(album)
            if tidal_album_tracks:
                logger.info(
                    f"✓ Found complete album with {len(tidal_album_tracks)} tracks "
                    f"on Tidal"
                )

                # Update results to include all tracks from the album
                updated_results = self._merge_album_tracks(
                    results, tidal_album_tracks, tracks
                )

                # Update conversion data with new matches
                for i, (discogs_track, tidal_track) in enumerate(updated_results):
                    if i < len(conversion_data["tracks"]):
                        # Update existing track data
                        track_data = self._create_track_conversion_data(
                            discogs_track, tidal_track
                        )
                        conversion_data["tracks"][i] = track_data

                # Log the improvement
                new_found_count = sum(1 for _, t in updated_results if t is not None)
                if new_found_count > found_count:
                    logger.info(
                        f"🎉 EP OPTIMIZATION SUCCESS: Improved from {found_count} to "
                        f"{new_found_count} tracks found!"
                    )

                results = updated_results
            else:
                logger.info(
                    "⚠️ EP optimization: Could not find complete album on Tidal"
                )

        # Write conversion data to file if specified
        if output_file:
            self._write_conversion_data(conversion_data, output_file)

        return results

    def _find_album_tracks(self, album: Album) -> Optional[List[tidalapi.Track]]:
        """Find all tracks for an album on Tidal."""
        if not album.primary_artist:
            return None

        # Create cache key
        album_title_norm = normalize_string(album.title)
        artist_name_norm = normalize_string(album.primary_artist.name)
        cache_key = f"{album_title_norm}_{artist_name_norm}"

        if cache_key in self.album_cache:
            return self.album_cache[cache_key]

        # Generate album search queries
        queries = self._generate_album_queries(album.title, album.primary_artist.name)

        for query in queries:
            logger.debug(f"  Searching for album: {query}")

            try:
                result = self.session.search(query)
                albums = result.get("albums", [])

                for tidal_album in albums:
                    if self._is_album_match(album, tidal_album):
                        logger.debug(f"  Found matching album: {tidal_album.name}")

                        # Get all tracks from this album
                        try:
                            tracks = tidal_album.tracks()
                            if tracks:
                                self.album_cache[cache_key] = tracks
                                return tracks
                        except Exception as e:
                            logger.warning(
                                f"Failed to fetch tracks for album "
                                f"{tidal_album.name}: {e}"
                            )
                            continue

            except Exception as e:
                logger.warning(f"Album search failed for query '{query}': {e}")
                continue

        # Cache negative result
        self.album_cache[cache_key] = None
        return None

    def _generate_album_queries(self, title: str, artist: str) -> List[str]:
        """Generate search queries for album search."""
        queries = []

        # Clean title and artist
        clean_title = self._clean_title(title)
        clean_artist = self._clean_artist(artist)

        # Primary queries
        queries.append(f'album:"{clean_title}" artist:"{clean_artist}"')
        queries.append(f"{clean_title} {clean_artist}")

        # Try with normalized strings
        norm_title = normalize_string(clean_title)
        norm_artist = normalize_string(clean_artist)

        if norm_title != clean_title or norm_artist != clean_artist:
            queries.append(f'album:"{norm_title}" artist:"{norm_artist}"')
            queries.append(f"{norm_title} {norm_artist}")

        return queries

    def _is_album_match(
        self, discogs_album: Album, tidal_album: tidalapi.Album
    ) -> bool:
        """Check if a Tidal album matches the Discogs album."""
        # Compare titles
        discogs_title = normalize_string(self._clean_title(discogs_album.title))
        tidal_title = normalize_string(self._clean_title(tidal_album.name))

        title_ratio = difflib.SequenceMatcher(None, discogs_title, tidal_title).ratio()

        # Compare primary artist
        primary_artist = discogs_album.primary_artist.name
        discogs_artist = normalize_string(self._clean_artist(primary_artist))
        tidal_artist = normalize_string(self._clean_artist(tidal_album.artist.name))

        artist_ratio = difflib.SequenceMatcher(
            None, discogs_artist, tidal_artist
        ).ratio()

        # Threshold for album matching (more lenient than track matching)
        return title_ratio > 0.8 and artist_ratio > 0.8

    def _match_track_in_album(
        self, discogs_track: Track, tidal_tracks: List[tidalapi.Track]
    ) -> Optional[tidalapi.Track]:
        """Match a specific track within a Tidal album's tracklist."""
        if not discogs_track.title:
            return None

        discogs_title = normalize_string(self._clean_title(discogs_track.title))
        discogs_artist = (
            normalize_string(self._clean_artist(discogs_track.primary_artist.name))
            if discogs_track.primary_artist
            else ""
        )

        best_match = None
        best_score = 0

        for tidal_track in tidal_tracks:
            tidal_title = normalize_string(self._clean_title(tidal_track.name))
            tidal_artist = normalize_string(self._clean_artist(tidal_track.artist.name))

            # Calculate similarity scores
            title_ratio = difflib.SequenceMatcher(
                None, discogs_title, tidal_title
            ).ratio()
            artist_ratio = difflib.SequenceMatcher(
                None, discogs_artist, tidal_artist
            ).ratio()

            # Weight title more heavily since we already know the album matches
            combined_score = (title_ratio * 0.7) + (artist_ratio * 0.3)

            # Also consider track position if available
            position_bonus = 0
            if (
                discogs_track.track_number
                and hasattr(tidal_track, "track_num")
                and tidal_track.track_num == discogs_track.track_number
            ):
                position_bonus = 0.1

            total_score = combined_score + position_bonus

            if total_score > best_score and title_ratio > 0.6:
                best_match = tidal_track
                best_score = total_score

        if best_match:
            logger.debug(
                f"    Matched: {discogs_track.title} -> {best_match.name} "
                f"(score: {best_score:.2f})"
            )
        else:
            logger.debug(f"    No match found for: {discogs_track.title}")

        return best_match

    def _merge_album_tracks(
        self,
        individual_results: List[Tuple[Track, Optional[tidalapi.Track]]],
        tidal_album_tracks: List[tidalapi.Track],
        discogs_tracks: List[Track],
    ) -> List[Tuple[Track, Optional[tidalapi.Track]]]:
        """
        Merge individually found tracks with complete album tracks.

        This method prioritizes individually found tracks (which are likely
        more accurate) but fills in missing tracks from the complete album.

        Args:
            individual_results: Results from individual track search
            tidal_album_tracks: All tracks from the Tidal album
            discogs_tracks: Original Discogs tracks

        Returns:
            Updated list of track pairs with improved matches
        """
        logger.debug(
            f"Merging {len(individual_results)} individual results with "
            f"{len(tidal_album_tracks)} album tracks"
        )

        merged_results = []

        for discogs_track, individually_found_track in individual_results:
            if individually_found_track:
                # Keep the individually found track (higher accuracy)
                merged_results.append((discogs_track, individually_found_track))
                logger.debug(f"  Keeping individual match: {discogs_track.title}")
            else:
                # Try to find this track in the complete album
                album_match = self._match_track_in_album(
                    discogs_track, tidal_album_tracks
                )
                if album_match:
                    logger.info(
                        f"  🆕 EP optimization found: '{discogs_track.title}' -> "
                        f"'{album_match.name}' (ID: {album_match.id})"
                    )
                else:
                    logger.debug(f"  Still no match: {discogs_track.title}")

                merged_results.append((discogs_track, album_match))

        return merged_results

    def find_track(self, track: Track) -> Optional[tidalapi.Track]:
        """
        Find a single track on Tidal using enhanced search strategy.

        Args:
            track: Track object to search for

        Returns:
            Tidal track if found, None otherwise
        """
        title = track.title
        artist = track.primary_artist.name if track.primary_artist else ""

        if not title or not artist:
            logger.warning(f"Skipping track with missing title or artist: {track}")
            return None

        logger.debug(f"Searching for: {title} by {artist}")

        # Generate search queries with increasing specificity
        queries = self._generate_track_queries(title, artist)

        # Try each query
        for search_query in queries:
            logger.debug(f"  Searching Tidal for: {search_query}")

            try:
                result = self.session.search(search_query)
                tracks = result.get("tracks", [])

                if not tracks:
                    logger.debug("    No tracks found")
                    continue

                # Find best match
                best_match = self._find_best_track_match(tracks, title, artist)
                if best_match:
                    return best_match

            except Exception as e:
                logger.warning(f"Search failed for query '{search_query}': {e}")
                continue

        logger.debug(f"  Not found on Tidal: {title} by {artist}")
        return None

    def _generate_track_queries(self, title: str, artist: str) -> List[str]:
        """Generate search queries for individual track search."""
        clean_title = self._clean_title(title)
        clean_artist = self._clean_artist(artist)

        queries = [
            f'track:"{clean_title}" artist:"{clean_artist}"',
            f"{clean_title} {clean_artist}",
            f"{normalize_string(clean_title)} {normalize_string(clean_artist)}",
        ]

        # Try without parenthetical content
        base_title = re.sub(r"\(.*?\)", "", clean_title).strip()
        if base_title != clean_title and base_title:
            queries.append(f'track:"{base_title}" artist:"{clean_artist}"')
            queries.append(f"{base_title} {clean_artist}")

        return queries

    def _clean_title(self, title: str) -> str:
        """Clean and normalize track/album title."""
        if not title:
            return ""

        # Remove common patterns that differ between platforms
        cleaned = title

        # Remove feat./featuring variations more aggressively
        cleaned = re.sub(r"\s*\(?\s*[Ff]eat\.?\s+[^)]*\)?", "", cleaned)
        cleaned = re.sub(r"\s*\(?\s*[Ff]eaturing\s+[^)]*\)?", "", cleaned)
        cleaned = re.sub(r"\s*\(?\s*[Ff]t\.?\s+[^)]*\)?", "", cleaned)

        # Remove all parenthetical content for fuzzy matching
        cleaned = re.sub(r"\s*\([^)]*\)", "", cleaned)

        # Remove square brackets content
        cleaned = re.sub(r"\s*\[[^\]]*\]", "", cleaned)

        # Remove common remix/version indicators that might differ
        remix_patterns = [
            r"\s*\-\s*[^-]*[Rr]emix[^-]*",
            r"\s*\-\s*[^-]*[Vv]ersion[^-]*",
            r"\s*\-\s*[^-]*[Mm]ix[^-]*",
            r"\s*\-\s*[^-]*[Ee]dit[^-]*",
            r"\s*\-\s*Original\s*$",
        ]

        for pattern in remix_patterns:
            cleaned = re.sub(pattern, "", cleaned)

        # Remove common suffixes
        cleaned = re.sub(r"\s*\-\s*Remastered.*$", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*\-\s*Radio.*$", "", cleaned, flags=re.IGNORECASE)

        # Clean up punctuation and whitespace
        cleaned = re.sub(r'[\'\""`]', "", cleaned)  # Remove quotes
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        return cleaned

    def _clean_artist(self, artist: str) -> str:
        """Clean and normalize artist name."""
        if not artist:
            return ""

        # Remove common variations
        cleaned = artist

        # Remove "Various Artists" and similar
        if cleaned.lower() in ["various artists", "various", "va"]:
            return ""

        # Remove parenthetical content like "(Original Artist)" or "(Remix)"
        cleaned = re.sub(r"\s*\([^)]*\)", "", cleaned)

        # Remove common prefixes that might differ between services
        cleaned = re.sub(r"^(The\s+)", "", cleaned, flags=re.IGNORECASE)

        # Remove featuring information that might be formatted differently
        cleaned = re.sub(
            r"\s+(feat\.?|featuring|ft\.?|f\.)\s+.*$", "", cleaned, flags=re.IGNORECASE
        )

        # Normalize ampersands and common variations
        cleaned = cleaned.replace("&", "and")
        cleaned = cleaned.replace(" + ", " and ")

        # Clean up whitespace
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        return cleaned

    def _find_best_track_match(
        self, tidal_tracks: List[tidalapi.Track], target_title: str, target_artist: str
    ) -> Optional[tidalapi.Track]:
        """Find the best matching track from Tidal search results."""
        norm_title = normalize_string(self._clean_title(target_title))
        norm_artist = normalize_string(self._clean_artist(target_artist))

        logger.debug(f"    Searching for: '{norm_title}' by '{norm_artist}'")
        logger.debug(f"    Found {len(tidal_tracks)} Tidal tracks to evaluate")

        # First pass: find tracks with decent artist matches (more lenient)
        artist_matches = []
        for tidal_track in tidal_tracks:
            t_artist = normalize_string(self._clean_artist(tidal_track.artist.name))
            artist_ratio = difflib.SequenceMatcher(None, t_artist, norm_artist).ratio()

            logger.debug(
                f"      Artist comparison: '{t_artist}' vs '{norm_artist}' "
                f"= {artist_ratio:.2f}"
            )

            if artist_ratio > 0.65:  # More lenient artist matching
                artist_matches.append((tidal_track, artist_ratio))

        if not artist_matches:
            logger.debug("    No decent artist match found (threshold: 0.65)")
            # Try even more lenient matching for difficult cases
            for tidal_track in tidal_tracks:
                t_artist = normalize_string(self._clean_artist(tidal_track.artist.name))
                artist_ratio = difflib.SequenceMatcher(
                    None, t_artist, norm_artist
                ).ratio()
                if artist_ratio > 0.5:  # Very lenient fallback
                    artist_matches.append((tidal_track, artist_ratio))

            if not artist_matches:
                logger.debug("    Still no match even with lenient threshold (0.5)")
                return None

        # Second pass: find best title match among artist matches
        best = None
        best_score = 0

        for tidal_track, artist_ratio in artist_matches:
            t_title = normalize_string(self._clean_title(tidal_track.name))
            title_ratio = difflib.SequenceMatcher(None, t_title, norm_title).ratio()
            # Weight title more heavily than artist
            score = (artist_ratio * 0.3) + (title_ratio * 0.7)

            logger.debug(
                f"      Tidal: '{tidal_track.name}' by '{tidal_track.artist.name}' "
                f"(artist_score={artist_ratio:.2f}, title_score={title_ratio:.2f}, "
                f"combined={score:.2f})"
            )

            if title_ratio > 0.6 and score > best_score:  # More lenient title matching
                best = tidal_track
                best_score = score

        if best:
            logger.debug(
                f"    ✓ Best match: '{best.name}' by '{best.artist.name}' "
                f"(id: {best.id}, score={best_score:.2f})"
            )
        else:
            logger.debug("    ✗ No satisfactory match found")

        return best

    def _create_track_conversion_data(
        self, discogs_track: Track, tidal_track: Optional[tidalapi.Track]
    ) -> Dict[str, Any]:
        """Create conversion data for a track."""
        data = {
            "discogs": {
                "title": discogs_track.title,
                "artists": [artist.name for artist in discogs_track.artists],
                "track_number": discogs_track.track_number,
                "duration": discogs_track.duration,
                "id": discogs_track.id,
            },
            "tidal": None,
            "matched": False,
        }

        if tidal_track:
            data["tidal"] = {
                "title": tidal_track.name,
                "artist": tidal_track.artist.name,
                "id": tidal_track.id,
                "duration": getattr(tidal_track, "duration", None),
                "track_number": getattr(tidal_track, "track_num", None),
            }
            data["matched"] = True

        return data

    def _write_conversion_data(self, data: Dict[str, Any], output_file: Path) -> None:
        """Write conversion data to a JSON file."""
        try:
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Load existing data if file exists
            existing_data = []
            if output_file.exists():
                try:
                    with open(output_file, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                        if content:
                            existing_data = json.loads(content)
                            if not isinstance(existing_data, list):
                                existing_data = [existing_data]
                except (json.JSONDecodeError, FileNotFoundError):
                    existing_data = []

            # Append new data
            existing_data.append(data)

            # Write back to file
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(existing_data, f, indent=2, ensure_ascii=False)

            logger.debug(f"Written conversion data to {output_file}")

        except Exception as e:
            logger.warning(f"Failed to write conversion data to {output_file}: {e}")

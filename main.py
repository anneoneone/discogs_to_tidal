import sys
import getpass
from discogs_client import Client as DiscogsClient
import tidalapi
import warnings
import os
from dotenv import load_dotenv
import time
import json
import re
import difflib

warnings.filterwarnings("ignore", category=SyntaxWarning)

load_dotenv()

def normalize_string(s):
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r"\(.*?\)|\[.*?\]", "", s)  # remove brackets
    s = re.sub(r"[^a-z0-9 ]", "", s)  # remove punctuation
    s = re.sub(r"\s+", " ", s).strip()  # collapse spaces
    return s

def extract_track_info(track):
    title = track.get('title')
    # Try to get artist from top-level, else from release
    artist = track.get('artist')
    if not artist:
        artist = None
        release = track.get('release', {})
        artists = release.get('artists', [])
        if artists and isinstance(artists, list):
            artist = artists[0].get('name')
    album = None
    year = None
    release = track.get('release', {})
    if release:
        album = release.get('title')
        year = release.get('year')
    return title, artist, album, year

# --- Discogs Integration ---
def get_discogs_tracks(user_token, cache_path="discogs_tracks.json"):
    print(f"Using Discogs token: {user_token[:6]}... (length: {len(user_token)})")
    # Try to load cached tracks
    if os.path.exists(cache_path):
        print(f"Loading cached Discogs tracks from {cache_path}...")
        try:
            with open(cache_path, "r") as f:
                tracks = json.load(f)
            print(f"Loaded {len(tracks)} tracks from cache.")
            return tracks
        except Exception as e:
            print(f"  Warning: Failed to load cache: {e}. Will refetch from Discogs.")
    d = DiscogsClient('DiscogsToTidalApp/1.0', user_token=user_token)
    try:
        user = d.identity()
    except Exception as e:
        print(f"Discogs authentication failed: {e}")
        sys.exit(1)
    print(f"Fetching collection for: {user.username}")
    tracks = []
    print("Fetching releases from your first collection folder...")
    for i, release in enumerate(user.collection_folders[0].releases):
        try:
            print(f"Processing release {i+1}: {release.release.title}")
            release_meta = release.release.data
            release_artists = release_meta.get('artists', [])
            for track in release.release.tracklist:
                track_meta = track.data.copy()
                track_meta['release'] = release_meta
                # Use track['artists'] if present, else release['artists']
                track_artists = track_meta.get('artists')
                if not track_artists:
                    track_artists = release_artists
                for artist_obj in track_artists:
                    entry = track_meta.copy()
                    entry['artist'] = artist_obj.get('name')
                    print(f"  Found track: {track_meta.get('title')} by {artist_obj.get('name')}")
                    tracks.append(entry)
        except Exception as e:
            print(f"  Warning: Failed to fetch release {i+1}: {e}")
        time.sleep(0.2)  # Small delay to avoid rate limits
    print(f"Total tracks fetched: {len(tracks)}")
    # Save to cache
    with open(cache_path, "w") as f:
        json.dump(tracks, f)
    print(f"Tracks saved to {cache_path}.")
    return tracks

# --- Tidal Integration ---
def tidal_login():
    token_path = os.path.expanduser("~/Documents/tidal_session.json")
    # Try to load existing OAuth session (token_type, access_token, refresh_token)
    if os.path.exists(token_path):
        print("Lade gespeichertes Tidal-Token...")
        with open(token_path, "r") as file:
            try:
                data = json.load(file)
                session = tidalapi.Session()
                session.load_oauth_session(data["token_type"], data["access_token"], data["refresh_token"])
                if session.check_login():
                    print("Erfolgreich mit gespeicherter Session angemeldet!")
                    return session
                else:
                    print("Gespeicherte Session ungültig, starte neuen Login...")
            except Exception as e:
                print(f"Fehler beim Laden des gespeicherten Tokens: {e}. Starte neuen Login...")
    # Neues Login, falls kein gültiger Token vorhanden ist
    session = tidalapi.Session()
    print("Bitte scanne den QR-Code oder öffne den Link zur Anmeldung:")
    print(session.login_oauth_simple())
    # Warte auf Authentifizierung und prüfe den Login-Status
    for _ in range(60):  # Warte bis zu 60 Sekunden
        if session.check_login():
            print("Erfolgreich angemeldet!")
            # Speichere die Session-Daten
            data = {
                "token_type": session.token_type,
                "access_token": session.access_token,
                "refresh_token": session.refresh_token,
            }
            with open(token_path, "w") as file:
                json.dump(data, file)
            print("Session-Daten gespeichert!")
            return session
        else:
            time.sleep(1)  # Warte 1 Sekunde und prüfe erneut
    raise Exception("Anmeldung fehlgeschlagen. Timeout nach 60 Sekunden.")

def tidal_search_tracks(session, query):
    try:
        result = session.search(query)
        if isinstance(result, dict) and 'tracks' in result:
            return result['tracks']
        return []
    except Exception as e:
        print(f"    Tidal search failed for query '{query}': {e}")
        return []

def fuzzy_match_track(tracks, norm_title, norm_artist):
    # Try exact match first
    for tidal_track in tracks:
        t_title = normalize_string(tidal_track.name)
        t_artist = normalize_string(tidal_track.artist.name)
        if t_title == norm_title and t_artist == norm_artist:
            return tidal_track, 'exact'
    # Fuzzy match: use difflib for close matches
    candidates = []
    for tidal_track in tracks:
        t_title = normalize_string(tidal_track.name)
        t_artist = normalize_string(tidal_track.artist.name)
        title_ratio = difflib.SequenceMatcher(None, t_title, norm_title).ratio()
        artist_ratio = difflib.SequenceMatcher(None, t_artist, norm_artist).ratio()
        if title_ratio > 0.8 and artist_ratio > 0.8:
            candidates.append((tidal_track, title_ratio + artist_ratio))
    if candidates:
        # Return best fuzzy match
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0], 'fuzzy'
    return None, None

def stepwise_tidal_search(session, title, artist):
    # Build search queries
    queries = [
        f"{title} {artist}",
        f"{normalize_string(title)} {normalize_string(artist)}",
    ]
    base_title = re.sub(r"\(.*?\)", "", title).strip()
    if base_title != title:
        queries.append(f"{base_title} {artist}")
    queries.append(base_title)
    queries.append(artist)
    norm_title = normalize_string(title)
    norm_artist = normalize_string(artist)
    for search_query in queries:
        print(f"  Searching Tidal for: {search_query}")
        result = session.search(search_query)
        tracks = result.get('tracks', [])
        # First, filter for strong artist match
        artist_matches = []
        for tidal_track in tracks:
            t_artist = normalize_string(tidal_track.artist.name)
            artist_ratio = difflib.SequenceMatcher(None, t_artist, norm_artist).ratio()
            if artist_ratio > 0.85:
                artist_matches.append((tidal_track, artist_ratio))
        if not artist_matches:
            print("    No strong artist match found. Aborting search for this query.")
            continue
        # Now, among strong artist matches, look for best track match (allowing lower threshold)
        best = None
        best_score = 0
        for tidal_track, artist_ratio in artist_matches:
            t_title = normalize_string(tidal_track.name)
            title_ratio = difflib.SequenceMatcher(None, t_title, norm_title).ratio()
            score = artist_ratio + title_ratio
            print(f"    Tidal: {tidal_track.name} by {tidal_track.artist.name} (id={tidal_track.id}, artist_score={artist_ratio:.2f}, title_score={title_ratio:.2f})")
            if title_ratio > 0.7 and score > best_score:
                best = tidal_track
                best_score = score
        if best:
            print(f"  Best match: {best.name} by {best.artist.name} (id: {best.id}, score={best_score:.2f})")
            return best
    return None

def add_tracks_to_playlist(session, playlist_name, tracks):
    print("Fetching your Tidal playlists...")
    try:
        playlists = session.user.playlists()
    except Exception as e:
        print(f"Error fetching playlists: {e}")
        playlists = []
    playlist = None
    for pl in playlists:
        if hasattr(pl, 'name') and pl.name == playlist_name:
            playlist = pl
            break
    if not playlist:
        print(f"Creating new playlist: {playlist_name}")
        playlist = session.user.create_playlist(playlist_name, "Imported from Discogs")
    print(f"Adding {len(tracks)} tracks to playlist '{playlist_name}'...")
    added_count = 0
    for idx, track in enumerate(tracks):
        title, artist, album, year = extract_track_info(track)
        if not title or not artist:
            print(f"  Skipping track with missing title or artist: {track}")
            continue
        print(f"Track {idx+1}/{len(tracks)}: {title} by {artist}")
        tidal_track = stepwise_tidal_search(session, title, artist)
        if tidal_track:
            playlist.add([tidal_track.id])
            added_count += 1
            print(f"    Added: {title} by {artist}")
        else:
            print(f"    Not found on Tidal: {title} by {artist}")
    print(f"Finished adding tracks to playlist. Total added: {added_count}")

# --- CLI Entry Point ---
def main():
    discogs_token = os.getenv("DISCOGS_TOKEN")
    if not discogs_token:
        print("Discogs token not found in .env file.")
        sys.exit(1)
    tracks = get_discogs_tracks(discogs_token)
    print(f"Found {len(tracks)} tracks in your Discogs collection.")
    session = tidal_login()
    playlist_name = input("Tidal playlist name to add tracks to: ")
    add_tracks_to_playlist(session, playlist_name, tracks)

if __name__ == "__main__":
    main()

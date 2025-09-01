import os
import json
import tidalapi
import difflib
import re

def normalize_string(s):
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r"\(.*?\)|\[.*?\]", "", s)  # remove brackets
    s = re.sub(r"[^a-z0-9 ]", "", s)  # remove punctuation
    s = re.sub(r"\s+", " ", s).strip()  # collapse spaces
    return s

def filter_release_tracks(discogs_tracks, release_id):
    """Return all tracks for a given release id."""
    return [
        t for t in discogs_tracks if t.get('release', {}).get('id') == release_id
    ]

def flatten_release_tracklist(release_tracks):
    """Flatten tracklist to [{artist, title, album, genre}] for the release."""
    # Only flatten the first (and only) release's tracklist, not all entries
    if not release_tracks:
        return []
    release = release_tracks[0].get('release', {})
    album = release.get('title')
    styles = release.get('styles', [])
    genre = styles
    tracklist = release.get('tracklist', [])
    flat_tracks = []
    for track in tracklist:
        title = track.get('title')
        artists = track.get('artists')
        if not artists:
            artists = release.get('artists', [])
        if artists:
            artist_obj = artists[0]
            artist = artist_obj.get('name')
        else:
            artist = None
        flat_tracks.append({
            'artist': artist,
            'title': title,
            'album': album,
            'genre': genre
        })
    return flat_tracks

def print_flat_tracks(flat_tracks, release_id):
    print(f"Flattened {len(flat_tracks)} tracks for release {release_id}:")
    for t in flat_tracks:
        genre_str = ', '.join(t['genre']) if t['genre'] else ''
        print(f"  {t['artist']} - {t['title']} [{t['album']}] ({genre_str})")

def tidal_login(token_path):
    session = tidalapi.Session()
    with open(token_path, "r") as f:
        creds = json.load(f)
    session.load_oauth_session(
        creds["token_type"],
        creds["access_token"],
        creds["refresh_token"]
    )
    if not session.check_login():
        print("Tidal login failed!")
        exit(1)
    print("Tidal login successful!")
    return session

def build_search_queries(title, artist):
    queries = [
        f"{title} {artist}",
        f"{normalize_string(title)} {normalize_string(artist)}",
    ]
    base_title = re.sub(r"\(.*?\)", "", title).strip()
    if base_title != title:
        queries.append(f"{base_title} {artist}")
    queries.append(base_title)
    queries.append(artist)
    return queries

def get_artist_matches(tidal_tracks, norm_artist):
    artist_matches = []
    for tidal_track in tidal_tracks:
        t_artist = normalize_string(tidal_track.artist.name)
        artist_ratio = difflib.SequenceMatcher(
            None, t_artist, norm_artist
        ).ratio()
        if artist_ratio > 0.85:
            artist_matches.append((tidal_track, artist_ratio))
    return artist_matches

def get_best_track_match(artist_matches, norm_title):
    best = None
    best_score = 0
    for tidal_track, artist_ratio in artist_matches:
        t_title = normalize_string(tidal_track.name)
        title_ratio = difflib.SequenceMatcher(
            None, t_title, norm_title
        ).ratio()
        score = artist_ratio + title_ratio
        print(
            f"    Tidal: {tidal_track.name} by {tidal_track.artist.name} "
            f"(id={tidal_track.id}, artist_score={artist_ratio:.2f}, "
            f"title_score={title_ratio:.2f})"
        )
        if title_ratio > 0.7 and score > best_score:
            best = tidal_track
            best_score = score
    return best, best_score

def find_best_tidal_match(session, title, artist):
    queries = build_search_queries(title, artist)
    norm_title = normalize_string(title)
    norm_artist = normalize_string(artist)
    for search_query in queries:
        print(f"  Searching Tidal for: {search_query}")
        result = session.search(search_query)
        tidal_tracks = result.get('tracks', [])
        artist_matches = get_artist_matches(tidal_tracks, norm_artist)
        if not artist_matches:
            print("    No strong artist match found. Aborting search for this query.")
            continue
        best, best_score = get_best_track_match(artist_matches, norm_title)
        if best:
            print(
                f"  Best match: {best.name} by {best.artist.name} "
                f"(id: {best.id}, score={best_score:.2f})"
            )
            return best
    print("  No good match found on Tidal.")
    return None

def search_and_match_tracks(session, tracks):
    for track in tracks:
        title = track.get('title')
        artist = track.get('artist')
        print(f"\nSearching for: {title} by {artist}")
        find_best_tidal_match(session, title, artist)

# --- MAIN EXECUTION ---
RELEASE_ID = 30019903
TOKEN_PATH = os.path.expanduser("~/Documents/tidal_session.json")

with open("discogs_tracks.json", "r") as f:
    discogs_tracks = json.load(f)

release_tracks = filter_release_tracks(discogs_tracks, RELEASE_ID)
print(f"Found {len(release_tracks)} tracks for release {RELEASE_ID}")
for t in release_tracks:
    print(f"  {t.get('title')} by {t.get('artist')}")

flat_tracks = flatten_release_tracklist(release_tracks)
print_flat_tracks(flat_tracks, RELEASE_ID)

session = tidal_login(TOKEN_PATH)
search_and_match_tracks(session, flat_tracks)

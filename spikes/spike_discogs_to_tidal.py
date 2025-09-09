import difflib
import json
import os

import tidalapi


def normalize_string(s):
    if not s:
        return ""
    import re

    s = s.lower()
    s = re.sub(r"\(.*?\)|\[.*?\]", "", s)  # remove brackets
    s = re.sub(r"[^a-z0-9 ]", "", s)  # remove punctuation
    s = re.sub(r"\s+", " ", s).strip()  # collapse spaces
    return s


# Load discogs_tracks.json
with open("discogs_tracks.json", "r") as f:
    discogs_tracks = json.load(f)

# Find the next example track
example = None
for t in discogs_tracks:
    title = t.get("title", "").lower()
    artist = t.get("artist")
    if not artist:
        release = t.get("release", {})
        artists = release.get("artists", [])
        if artists and isinstance(artists, list):
            artist = artists[0].get("name")
    if artist:
        artist = artist.lower()
    if "black shampoo" in title and "e tones" in artist:
        example = t
        break
if not example:
    print("Example track not found in discogs_tracks.json!")
    exit(1)
print(f"Example track: {example.get('title')} by {artist}")

# Prepare Tidal session
TOKEN_PATH = os.path.expanduser("~/Documents/tidal_session.json")
session = tidalapi.Session()
with open(TOKEN_PATH, "r") as f:
    creds = json.load(f)
session.load_oauth_session(
    creds["token_type"], creds["access_token"], creds["refresh_token"]
)
if not session.check_login():
    print("Tidal login failed!")
    exit(1)
print("Tidal login successful!")

# Stepwise fallback search
search_queries = [
    f"{example.get('title')} {artist}",
    f"{normalize_string(example.get('title'))} {normalize_string(artist)}",
]
import re

base_title = re.sub(r"\(.*?\)", "", example.get("title")).strip()
if base_title != example.get("title"):
    search_queries.append(f"{base_title} {artist}")
search_queries.append(base_title)
search_queries.append(artist)

found_any = False
for search_query in search_queries:
    print(f"\nSearching Tidal for: {search_query}")
    result = session.search(search_query)
    tracks = result.get("tracks", [])
    print(f"Found {len(tracks)} tracks on Tidal.")
    norm_title = normalize_string(example.get("title"))
    norm_artist = normalize_string(artist)
    best = None
    best_score = 0
    for tidal_track in tracks:
        t_title = normalize_string(tidal_track.name)
        t_artist = normalize_string(tidal_track.artist.name)
        title_ratio = difflib.SequenceMatcher(None, t_title, norm_title).ratio()
        artist_ratio = difflib.SequenceMatcher(None, t_artist, norm_artist).ratio()
        score = title_ratio + artist_ratio
        print(
            f"  Tidal: {tidal_track.name} by {tidal_track.artist.name} (id={tidal_track.id}, score={score:.2f})"
        )
        if score > best_score:
            best = tidal_track
            best_score = score
    if best and best_score > 1.5:
        print(
            f"Best match: {best.name} by {best.artist.name} (id: {best.id}, score={best_score:.2f})"
        )
        if str(best.id) == "298879651":
            print("  This matches the provided Tidal track ID!")
        found_any = True
        break
if not found_any:
    print("No good match found on Tidal.")

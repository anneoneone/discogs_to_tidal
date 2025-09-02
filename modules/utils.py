import re
import difflib

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


def fuzzy_match_track(tracks, norm_title, norm_artist):
    for tidal_track in tracks:
        t_title = normalize_string(tidal_track.name)
        t_artist = normalize_string(tidal_track.artist.name)
        if t_title == norm_title and t_artist == norm_artist:
            return tidal_track, 'exact'
    candidates = []
    for tidal_track in tracks:
        t_title = normalize_string(tidal_track.name)
        t_artist = normalize_string(tidal_track.artist.name)
        title_ratio = difflib.SequenceMatcher(None, t_title, norm_title).ratio()
        artist_ratio = difflib.SequenceMatcher(None, t_artist, norm_artist).ratio()
        if title_ratio > 0.8 and artist_ratio > 0.8:
            candidates.append((tidal_track, title_ratio + artist_ratio))
    if candidates:
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0], 'fuzzy'
    return None, None

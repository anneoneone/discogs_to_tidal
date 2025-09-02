import os
import time
import json
import tidalapi
from .utils import normalize_string, extract_track_info

def tidal_login():
    token_path = os.path.expanduser("~/Documents/tidal_session.json")
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
    session = tidalapi.Session()
    print("Bitte scanne den QR-Code oder öffne den Link zur Anmeldung:")
    print(session.login_oauth_simple())
    for _ in range(60):
        if session.check_login():
            print("Erfolgreich angemeldet!")
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
            time.sleep(1)
    raise Exception("Anmeldung fehlgeschlagen. Timeout nach 60 Sekunden.")

def stepwise_tidal_search(session, title, artist):
    import re
    import difflib
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
        artist_matches = []
        for tidal_track in tracks:
            t_artist = normalize_string(tidal_track.artist.name)
            artist_ratio = difflib.SequenceMatcher(None, t_artist, norm_artist).ratio()
            if artist_ratio > 0.85:
                artist_matches.append((tidal_track, artist_ratio))
        if not artist_matches:
            print("    No strong artist match found. Aborting search for this query.")
            continue
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

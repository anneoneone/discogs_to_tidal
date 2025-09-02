import os
import sys
import time
import json
from discogs_client import Client as DiscogsClient

def get_discogs_tracks(user_token, cache_path="discogs_tracks.json"):
    print(f"Using Discogs token: {user_token[:6]}... (length: {len(user_token)})")
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
        time.sleep(0.2)
    print(f"Total tracks fetched: {len(tracks)}")
    with open(cache_path, "w") as f:
        json.dump(tracks, f)
    print(f"Tracks saved to {cache_path}.")
    return tracks

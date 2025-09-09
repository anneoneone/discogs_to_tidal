import os
import time

import tidalapi

# Use your existing token file
TOKEN_PATH = os.path.expanduser("~/Documents/tidal_session.json")

# Load session from token file
session = tidalapi.Session()
with open(TOKEN_PATH, "r") as f:
    data = f.read()
import json

creds = json.loads(data)
session.load_oauth_session(
    creds["token_type"], creds["access_token"], creds["refresh_token"]
)
if not session.check_login():
    print("Tidal login failed!")
    exit(1)
print("Tidal login successful!")

# Find playlist named "House"
playlists = session.user.playlists()
playlist = None
for pl in playlists:
    if hasattr(pl, "name") and pl.name == "House":
        playlist = pl
        break
if not playlist:
    print("Playlist 'House' not found!")
    exit(1)
print(f"Found playlist: {playlist.name}")

# Search for a common song (e.g. 'Daft Punk One More Time')
search_query = "Daft Punk One More Time"
result = session.search(search_query)
print("Search result type:", type(result))
if isinstance(result, dict):
    print("Search result keys:", list(result.keys()))
    for key, value in result.items():
        if isinstance(value, list):
            print(f"  {key}: list of length {len(value)}")
            if len(value) > 0:
                print(f"    First item: {value[0]}")
        elif isinstance(value, dict):
            print(f"  {key}: dict with keys {list(value.keys())}")
        else:
            print(f"  {key}: {type(value)}")
else:
    print("Result is not a dict!")
# Try to get tracks from common keys
tracks = []
for key in ["tracks", "items", "results"]:
    if key in result and isinstance(result[key], list):
        tracks = result[key]
        break
if not tracks:
    print(f"No tracks found for '{search_query}'!")
    exit(1)
track = tracks[0]
print(f"Found track: {track}")

# Add track to playlist
playlist.add([track.id])
print(f"Added '{track.name}' to playlist '{playlist.name}'!")

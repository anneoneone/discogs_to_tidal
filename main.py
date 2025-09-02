import sys
import os
from dotenv import load_dotenv
from modules.discogs_integration import get_discogs_tracks
from modules.tidal_integration import tidal_login, add_tracks_to_playlist


def main():
    load_dotenv()
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

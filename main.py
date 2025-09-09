#!/usr/bin/env python3
"""
Legacy main.py entry point for backward compatibility.
Now uses the new package structure.
"""
import sys
from pathlib import Path

# Add src to path for development
src_path = Path(__file__).parent / "src"
if src_path.exists():
    sys.path.insert(0, str(src_path))

from dotenv import load_dotenv
from discogs_to_tidal.core.config import Config
from discogs_to_tidal.integrations.discogs import DiscogsService
from discogs_to_tidal.integrations.tidal import TidalService


def main():
    """Main function using the new package structure."""
    print("🎵 Discogs to Tidal Sync (Legacy Interface)")
    print("=" * 50)
    
    # Load environment
    load_dotenv()
    
    try:
        # Create configuration
        config = Config.from_env()
        
        if not config.discogs_token:
            print("❌ Discogs token not found in .env file.")
            print("   Please set DISCOGS_TOKEN in your .env file.")
            sys.exit(1)
        
        # Initialize services
        print("🔐 Initializing services...")
        discogs_service = DiscogsService(config)
        tidal_service = TidalService(config)
        
        # Authenticate with Discogs
        print("🔐 Authenticating with Discogs...")
        discogs_service.authenticate()
        
        # Get tracks from Discogs
        print("📀 Fetching tracks from your Discogs collection...")
        tracks = discogs_service.get_collection_tracks()
        
        if not tracks:
            print("❌ No tracks found in your Discogs collection.")
            sys.exit(1)
        
        print(f"✅ Found {len(tracks)} tracks in your Discogs collection.")
        
        # Authenticate with Tidal
        print("🔐 Authenticating with Tidal...")
        tidal_service.session  # This triggers authentication
        
        # Get playlist name
        playlist_name = input("\n🎶 Enter Tidal playlist name to add tracks to: ")
        if not playlist_name.strip():
            playlist_name = "My Discogs Collection"
            print(f"Using default playlist name: {playlist_name}")
        
        # Add tracks to playlist
        print(f"\n🎵 Adding tracks to playlist '{playlist_name}'...")
        result = tidal_service.add_tracks_to_playlist(playlist_name, tracks)
        
        # Display results
        print(f"\n📊 Sync Results:")
        print(f"  Total tracks: {result.total_tracks}")
        print(f"  Found on Tidal: {result.found_tracks}")
        print(f"  Added to playlist: {result.added_tracks}")
        print(f"  Failed: {result.failed_tracks}")
        
        success_rate = (
            result.added_tracks / result.total_tracks * 100
        ) if result.total_tracks > 0 else 0
        print(f"  Success rate: {success_rate:.1f}%")
        
        if result.failed_tracks > 0:
            print(f"\n⚠️  {result.failed_tracks} tracks could not be found on Tidal")
        
        print(f"\n✅ Sync completed! Playlist '{playlist_name}' updated.")
        print("\n💡 Advanced features available:")
        print("   discogs-to-tidal sync       - Full sync with options")
        print("   discogs-to-tidal style-sync - Create playlists by style/subgenre")
        print("   discogs-to-tidal --help     - See all available commands")
        
    except KeyboardInterrupt:
        print("\n\n❌ Sync cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\n💡 For better error handling, try the new CLI interface:")
        print("   discogs-to-tidal sync")
        sys.exit(1)


if __name__ == "__main__":
    main()

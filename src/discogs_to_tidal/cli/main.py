"""
Command-line interface for Discogs to Tidal sync.
"""
import logging
from pathlib import Path
from typing import Optional

import click

from discogs_to_tidal.integrations.tidal.client import TidalService

from ..core.config import Config
from ..core.exceptions import DiscogsToTidalError
from ..core.sync import SyncService
from ..integrations.discogs.client import DiscogsService
from ..integrations.tidal.auth import TidalAuth


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.option("--debug", is_flag=True, help="Enable debug logging")
@click.pass_context
def cli(ctx: click.Context, verbose: bool, debug: bool) -> None:
    """Discogs to Tidal playlist sync tool."""
    # Ensure context object exists
    ctx.ensure_object(dict)

    # Configure logging
    level = logging.DEBUG if debug else (logging.INFO if verbose else logging.WARNING)
    logging.basicConfig(
        level=level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Store config in context
    try:
        ctx.obj["config"] = Config.from_env()
    except Exception as e:
        click.echo(f"Error loading configuration: {e}", err=True)
        ctx.exit(1)


@cli.command()
@click.option(
    "--playlist-name",
    "-p",
    default="My Discogs Collection",
    help="Name for the Tidal playlist",
)
@click.option(
    "--folder-id",
    "-f",
    default=0,
    type=int,
    help="Discogs collection folder ID (0 = All)",
)
@click.option(
    "--limit",
    "-l",
    default=None,
    type=click.IntRange(1, None),
    help="Maximum number of tracks to sync",
)
@click.option(
    "--dry-run", is_flag=True, help="Show what would be synced without making changes"
)
@click.pass_context
def sync(
    ctx: click.Context,
    playlist_name: str,
    folder_id: int,
    limit: Optional[int],
    dry_run: bool,
) -> None:
    """Sync Discogs collection to Tidal playlist."""
    config = ctx.obj["config"]

    click.echo(f"🎵 Syncing Discogs collection to Tidal playlist: {playlist_name}")
    click.echo(f"📁 Folder ID: {folder_id}")
    if limit:
        click.echo(f"🔢 Limit: {limit} tracks")
    if dry_run:
        click.echo("🧪 Dry run mode: No tracks will be added")

    try:
        # Initialize services
        discogs_service = DiscogsService(config)
        tidal_auth = TidalAuth(config)
        sync_service = SyncService(discogs_service, tidal_auth)

        # Set up progress callback for better UX
        def auth_progress(message: str, progress: int) -> None:
            if progress <= 30:
                click.echo(f"🔐 {message}")
            elif progress <= 90:
                click.echo(f"⏳ {message}")
            else:
                click.echo(f"✅ {message}")

        # Pre-authenticate to provide better user experience
        click.echo("🔐 Authenticating with Tidal...")
        tidal_auth.authenticate()

        # Set up progress callback
        def progress_callback(message: str) -> None:
            click.echo(f"⏳ {message}")

        # Perform sync
        result = sync_service.sync_collection(
            progress_callback=progress_callback,
            playlist_name=playlist_name,
            folder_id=folder_id,
        )

        # Display results
        click.echo("\n📊 Sync Results:")
        click.echo(f"  Total tracks: {result.total_tracks}")
        click.echo(f"  Found on Tidal: {result.found_tracks}")
        if dry_run:
            click.echo(f"  Would add: {result.found_tracks}")
        else:
            click.echo(f"  Added to playlist: {result.added_tracks}")
        click.echo(f"  Failed: {result.failed_tracks}")

        success_rate = (
            (result.found_tracks / result.total_tracks * 100)
            if result.total_tracks > 0
            else 0
        )
        click.echo(f"  Success rate: {success_rate:.1f}%")

        if result.failed_tracks > 0:
            click.echo(
                f"\n⚠️  {result.failed_tracks} tracks could not be found on Tidal"
            )

        if dry_run:
            click.echo(
                f"\n✅ Dry run completed! {result.found_tracks} tracks "
                f"would be added to '{playlist_name}'."
            )
        else:
            click.echo(
                f"\n✅ Sync completed! Playlist '{playlist_name}' "
                f"updated with {result.added_tracks} tracks."
            )

    except DiscogsToTidalError as e:
        click.echo(f"❌ Sync failed: {e}", err=True)
        ctx.exit(1)
    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}", err=True)
        ctx.exit(1)


@cli.command()
@click.pass_context
def test_auth(ctx: click.Context) -> None:
    """Test authentication with both services using improved authentication flow."""
    config = ctx.obj["config"]

    try:
        # Test Discogs
        click.echo("🔐 Testing Discogs authentication...")
        discogs_service = DiscogsService(config)
        discogs_service.authenticate()
        click.echo("✅ Discogs authentication successful")

        # Test Tidal with progress feedback
        click.echo("\n🔐 Testing Tidal authentication with progress feedback...")
        click.echo("=" * 50)

        tidal_service = TidalService(config)

        # Set up progress callback for authentication
        def auth_progress(message: str, progress: int) -> None:
            if progress <= 30:
                click.echo(f"🔐 {message}")
            elif progress <= 90:
                click.echo(f"⏳ {message}")
            else:
                click.echo(f"✅ {message}")

        # Test new authentication with progress
        if tidal_service.authenticate_with_progress(auth_progress):
            click.echo("🎉 Tidal authentication successful!")

            # Show some basic info if available
            if hasattr(tidal_service, "session") and tidal_service.session:
                try:
                    user = tidal_service.session.user
                    if user:
                        click.echo(f"👤 Logged in as: {user.id}")
                        country = getattr(user, "country_code", "Unknown")
                        click.echo(f"🌍 Country: {country}")
                except Exception as e:
                    click.echo(f"ℹ️ User info not available: {e}")
        else:
            click.echo("❌ Tidal authentication failed!")
            ctx.exit(1)

        click.echo("\n🎉 Both services authenticated successfully!")

    except DiscogsToTidalError as e:
        click.echo(f"❌ Authentication failed: {e}", err=True)
        ctx.exit(1)
    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}", err=True)
        ctx.exit(1)


@cli.command()
@click.pass_context
def config_info(ctx: click.Context) -> None:
    """Display configuration information."""
    config = ctx.obj["config"]

    click.echo("⚙️  Configuration:")
    click.echo(f"  Discogs token: {'✅ Set' if config.discogs_token else '❌ Not set'}")
    max_tracks_display = config.max_tracks if config.max_tracks > 0 else "No limit"
    click.echo(f"  Max tracks: {max_tracks_display}")
    click.echo(f"  Tokens directory: {config.tokens_dir}")
    click.echo(f"  Log level: {config.log_level}")

    # Check for .env file
    env_file = Path(".env")
    if env_file.exists():
        click.echo("  Environment file: ✅ Found (.env)")
    else:
        click.echo("  Environment file: ❌ Not found (.env)")
        click.echo("    Create a .env file with your DISCOGS_TOKEN")


@cli.command()
@click.pass_context
def list_folders(ctx: click.Context) -> None:
    """List available Discogs collection folders."""
    config = ctx.obj["config"]

    try:
        # Initialize Discogs service
        discogs_service = DiscogsService(config)
        discogs_service.authenticate()

        click.echo("📁 Discogs Collection Folders:")
        click.echo("=" * 40)

        folders = discogs_service.get_collection_folders()

        if not folders:
            click.echo("No folders found in your Discogs collection.")
            return

        for folder in folders:
            folder_line = (
                f"  ID: {folder['id']:>3} | {folder['name']:<20} | "
                f"{folder['count']:>4} items"
            )
            click.echo(folder_line)

        click.echo("=" * 40)
        click.echo(
            "💡 Use --folder-id <ID> with the sync command to sync a specific folder"
        )

    except DiscogsToTidalError as e:
        click.echo(f"❌ Failed to list folders: {e}", err=True)
        ctx.exit(1)
    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}", err=True)
        ctx.exit(1)


@cli.command()
@click.pass_context
def tidal_auth(ctx: click.Context) -> None:
    """Check Tidal authorization status and authenticate if needed."""
    config = ctx.obj["config"]

    try:
        click.echo("🔐 Checking Tidal authorization status...")

        # Initialize Tidal auth
        tidal_auth = TidalAuth(config)

        # Check for existing valid session
        session_data = tidal_auth.load_session()
        if session_data:
            click.echo("📄 Found existing session data")

            # Try to validate existing session
            try:
                session = tidal_auth._try_existing_session()
                if session:
                    click.echo("✅ Existing Tidal session is valid!")

                    # Show user info if available
                    if hasattr(session, "user") and session.user:
                        try:
                            user_id = getattr(session.user, "id", "Unknown")
                            country = getattr(session.user, "country_code", "Unknown")
                            click.echo(f"👤 Logged in as: {user_id}")
                            click.echo(f"🌍 Country: {country}")
                        except Exception:
                            click.echo("👤 User info not available")

                    click.echo("🎉 No authentication needed - you're all set!")
                    return
                else:
                    click.echo("⚠️ Existing session is invalid or expired")
            except Exception as e:
                click.echo(f"⚠️ Could not validate existing session: {e}")
        else:
            click.echo("📭 No existing session found")

        # Need to authenticate
        click.echo("\n🔐 Starting Tidal authentication process...")
        click.echo("=" * 50)

        # Set up progress callback
        def auth_progress(message: str, progress: int) -> None:
            if progress <= 30:
                click.echo(f"🔐 {message}")
            elif progress <= 90:
                click.echo(f"⏳ {message}")
            else:
                click.echo(f"✅ {message}")

        tidal_auth.set_progress_callback(auth_progress)

        # Perform authentication
        session = tidal_auth.authenticate(force_new=True)

        if session and tidal_auth.validate_session(session):
            click.echo("\n🎉 Tidal authentication successful!")

            # Show user info
            if hasattr(session, "user") and session.user:
                try:
                    user_id = getattr(session.user, "id", "Unknown")
                    country = getattr(session.user, "country_code", "Unknown")
                    click.echo(f"👤 Logged in as: {user_id}")
                    click.echo(f"🌍 Country: {country}")
                except Exception:
                    click.echo("👤 User info not available")

            click.echo("💾 Session saved for future use")
            click.echo("✨ You can now use 'make sync' to sync your music!")
        else:
            click.echo("❌ Authentication failed!")
            ctx.exit(1)

    except DiscogsToTidalError as e:
        click.echo(f"❌ Authentication error: {e}", err=True)
        ctx.exit(1)
    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}", err=True)
        ctx.exit(1)


if __name__ == "__main__":
    cli()

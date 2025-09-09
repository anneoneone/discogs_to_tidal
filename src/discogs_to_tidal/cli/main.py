"""
Command-line interface for Discogs to Tidal sync.
"""
import logging
from pathlib import Path

import click

from discogs_to_tidal.integrations.tidal.client import TidalService

from ..core.config import Config
from ..core.exceptions import DiscogsToTidalError
from ..integrations.discogs.client import DiscogsService
from ..integrations.tidal.auth import TidalAuth
from .sync_command import execute_sync_command


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
    default=None,
    type=int,
    help="Discogs collection folder ID (skip for interactive selection)",
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
def sync(ctx, playlist_name, folder_id, limit, dry_run):
    """Sync Discogs collection to Tidal playlist."""
    config = ctx.obj["config"]
    execute_sync_command(config, playlist_name, folder_id, limit, dry_run)


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


@cli.command()
@click.pass_context
def discogs_auth(ctx: click.Context) -> None:
    """Check Discogs authorization status and setup token if needed."""
    config = ctx.obj["config"]

    try:
        click.echo("🔐 Checking Discogs authorization status...")

        # Check for existing token
        existing_token = config.get_discogs_token()
        if existing_token:
            click.echo("📄 Found existing Discogs token")

            # Test the existing token
            click.echo("🔍 Validating existing token...")
            try:
                from ..integrations.discogs.client import DiscogsService

                discogs_service = DiscogsService(config)
                discogs_service.authenticate()

                # Get user info to confirm token works
                user = discogs_service.user
                if user:
                    username = getattr(user, "username", "Unknown")
                    num_collection = getattr(user, "num_collection", "Unknown")
                    click.echo("✅ Existing Discogs token is valid!")
                    click.echo(f"👤 Logged in as: {username}")
                    click.echo(f"📊 Collection items: {num_collection}")
                    click.echo("🎉 No authentication needed - you're all set!")
                    return
                else:
                    raise Exception("Could not retrieve user information")

            except Exception as e:
                click.echo(f"⚠️ Existing token validation failed: {e}")
                click.echo("🔄 Will prompt for new token...")
        else:
            click.echo("📭 No existing Discogs token found")

        # Need to get a new token
        click.echo("\n🔑 Discogs Personal Access Token Setup")
        click.echo("=" * 50)
        click.echo("To use this tool, you need a personal access token from Discogs.")
        click.echo("")
        click.echo("📋 Steps to get your token:")
        click.echo("  1. Go to: https://www.discogs.com/settings/developers")
        click.echo("  2. Click 'Generate new token'")
        click.echo("  3. Copy the generated token")
        click.echo("  4. Paste it below")
        click.echo("")

        # Prompt for token
        while True:
            token = click.prompt(
                "🔑 Enter your Discogs personal access token", type=str, hide_input=True
            ).strip()

            if not token:
                click.echo("❌ Token cannot be empty. Please try again.")
                continue

            # Validate the token
            click.echo("🔍 Validating token...")
            try:
                # Create a temporary config with the new token
                test_config = Config(
                    discogs_token=token,
                    log_level=config.log_level,
                    max_tracks=config.max_tracks,
                )

                from ..integrations.discogs.client import DiscogsService

                discogs_service = DiscogsService(test_config)
                discogs_service.authenticate()

                # Test by getting user info
                user = discogs_service.user
                if not user:
                    raise Exception("Could not retrieve user information")

                username = getattr(user, "username", "Unknown")
                num_collection = getattr(user, "num_collection", "Unknown")

                # Token is valid and session was saved by authentication process
                click.echo("✅ Token validation successful!")
                click.echo(f"👤 Logged in as: {username}")
                click.echo(f"📊 Collection items: {num_collection}")
                click.echo("💾 Session saved securely for future use")
                click.echo("✨ You can now use 'make sync' to sync your music!")
                break

            except Exception as e:
                click.echo(f"❌ Token validation failed: {e}")
                click.echo("💡 Please check that:")
                click.echo("  - The token is copied correctly (no extra spaces)")
                click.echo("  - The token has not expired")
                click.echo("  - You have an active internet connection")

                retry = click.confirm("🔄 Would you like to try another token?")
                if not retry:
                    click.echo("❌ Authentication setup cancelled")
                    ctx.exit(1)

    except KeyboardInterrupt:
        click.echo("\n❌ Authentication setup cancelled by user")
        ctx.exit(1)
    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}", err=True)
        ctx.exit(1)


if __name__ == "__main__":
    cli()

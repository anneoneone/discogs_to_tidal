"""
CLI-specific logic for the sync command.

This module contains all the CLI presentation logic, user interaction,
and formatting for the sync command, while delegating the actual sync
business logic to the core SyncService.
"""
from typing import Callable, Optional, Tuple

import click

from ..core.config import Config
from ..core.exceptions import DiscogsToTidalError
from ..core.models import SyncResult
from ..core.sync import SyncService
from ..integrations.discogs.client import DiscogsService
from ..integrations.tidal.auth import TidalAuth


def initialize_services(
    config: Config,
) -> Tuple[DiscogsService, TidalAuth, SyncService]:
    """Initialize and return Discogs and Tidal services."""
    try:
        discogs_service = DiscogsService(config)
        tidal_auth = TidalAuth(config)
        sync_service = SyncService(discogs_service, tidal_auth)
        return discogs_service, tidal_auth, sync_service
    except Exception as e:
        raise DiscogsToTidalError(f"Failed to initialize services: {e}")


def select_discogs_folder(discogs_service: DiscogsService) -> int:
    """Interactive folder selection for Discogs collection."""
    click.echo("\n📁 Discovering your Discogs collection folders...")
    
    try:
        # Authenticate first
        discogs_service.authenticate()
        
        # Get available folders
        folders = discogs_service.get_collection_folders()
        
        if not folders:
            click.echo("❌ No folders found in your Discogs collection.")
            return 0
        
        # Display folders with array index mapping but return actual folder IDs
        click.echo("\n📋 Available Discogs folders:")
        click.echo("=" * 70)
        click.echo(f"{'Index':<8} | {'Folder Name':<30} | {'Items':<10}")
        click.echo("-" * 70)
        
        # Create mapping between display index and actual folder ID
        index_to_folder_id = {}
        for i, folder in enumerate(folders):
            folder_line = (
                f"{i:<8} | {folder['name']:<30} | "
                f"{folder['count']:>4} items"
            )
            click.echo(folder_line)
            # Map display index to actual Discogs folder ID
            index_to_folder_id[i] = folder['id']
        
        click.echo("=" * 70)
        click.echo("💡 Use the Index number to select a folder")
        
        # Get user selection
        while True:
            try:
                folder_choice = click.prompt(
                    "\n🎯 Select folder Index to sync",
                    type=int,
                    default=0
                )
                
                # Validate choice using array indices
                if folder_choice in index_to_folder_id:
                    actual_folder_id = index_to_folder_id[folder_choice]
                    selected_folder = folders[folder_choice]
                    folder_info = (
                        f"✅ Selected: {selected_folder['name']} "
                        f"({selected_folder['count']} items)"
                    )
                    click.echo(folder_info)
                    # Return the actual Discogs folder ID (not the array index)
                    return actual_folder_id
                else:
                    valid_indices = list(range(len(folders)))
                    valid_indices_str = ', '.join(map(str, valid_indices))
                    click.echo(
                        f"❌ Invalid folder index. Choose from: {valid_indices_str}"
                    )
            
            except click.Abort:
                click.echo("\n❌ Folder selection cancelled.")
                raise click.ClickException("Folder selection required for sync.")
            except (ValueError, TypeError):
                click.echo("❌ Please enter a valid number.")
    
    except Exception as e:
        click.echo(f"❌ Error fetching folders: {e}")
        click.echo("💡 Using default folder (All items)")
        return 0


def resolve_folder_selection(
    discogs_service: DiscogsService, folder_id: Optional[int]
) -> int:
    """Resolve folder selection through interactive selection or validation."""
    try:
        if folder_id is None:
            return select_discogs_folder(discogs_service)
        
        # Validate provided folder_id exists
        folders = discogs_service.get_collection_folders()
        valid_folder_ids = {folder['id'] for folder in folders}
        
        if folder_id not in valid_folder_ids:
            available = ', '.join(f"ID {fid}" for fid in sorted(valid_folder_ids))
            raise DiscogsToTidalError(
                f"Invalid folder ID {folder_id}. Available: {available}"
            )
        
        return folder_id
    except DiscogsToTidalError:
        raise
    except Exception as e:
        raise DiscogsToTidalError(f"Failed to resolve folder selection: {e}")


def display_folder_info(discogs_service: DiscogsService, folder_id: int) -> None:
    """Display information about the selected folder."""
    try:
        folders = discogs_service.get_collection_folders()
        selected_folder = next(
            (f for f in folders if f['id'] == folder_id), None
        )
        
        if selected_folder:
            click.echo(
                f"📁 Selected Folder: {selected_folder['name']} "
                f"({selected_folder['count']} items)"
            )
        else:
            click.echo(f"📁 Selected Folder ID: {folder_id}")
    except Exception:
        # Non-critical error, just show folder ID
        click.echo(f"📁 Selected Folder ID: {folder_id}")


def display_sync_parameters(
    playlist_name: str, limit: Optional[int], dry_run: bool
) -> None:
    """Display sync parameters to user."""
    if limit:
        click.echo(f"🔢 Limit: {limit} tracks")
    if dry_run:
        click.echo("🧪 Dry run mode: No tracks will be added")


def setup_progress_callbacks() -> Tuple[
    Callable[[str, int], None], Callable[[str], None]
]:
    """Setup progress callback functions for authentication and sync."""
    def auth_progress(message: str, progress: int) -> None:
        if progress <= 30:
            click.echo(f"🔐 {message}")
        elif progress <= 90:
            click.echo(f"⏳ {message}")
        else:
            click.echo(f"✅ {message}")

    def progress_callback(message: str) -> None:
        click.echo(f"⏳ {message}")
    
    return auth_progress, progress_callback


def authenticate_services(tidal_auth: TidalAuth) -> None:
    """Authenticate with external services."""
    try:
        click.echo("🔐 Authenticating with Tidal...")
        tidal_auth.authenticate()
    except Exception as e:
        raise DiscogsToTidalError(f"Tidal authentication failed: {e}")


def perform_sync(
    sync_service: SyncService,
    progress_callback: Callable[[str], None],
    playlist_name: str,
    folder_id: int,
) -> SyncResult:
    """Perform the actual synchronization."""
    try:
        return sync_service.sync_collection(
            progress_callback=progress_callback,
            playlist_name=playlist_name,
            folder_id=folder_id,
        )
    except Exception as e:
        raise DiscogsToTidalError(f"Sync operation failed: {e}")


def display_sync_results(result: SyncResult, dry_run: bool) -> None:
    """Display comprehensive sync results to user."""
    click.echo("\n📊 Sync Results:")
    click.echo(f"  Total tracks: {result.total_tracks}")
    click.echo(f"  Found on Tidal: {result.found_tracks}")
    
    if dry_run:
        click.echo(f"  Would add: {result.found_tracks}")
    else:
        click.echo(f"  Added to playlist: {result.added_tracks}")
    
    click.echo(f"  Failed: {result.failed_tracks}")

    # Calculate and display success rate
    success_rate = (
        (result.found_tracks / result.total_tracks * 100)
        if result.total_tracks > 0
        else 0
    )
    click.echo(f"  Success rate: {success_rate:.1f}%")

    # Show warnings and completion messages
    if result.failed_tracks > 0:
        click.echo(
            f"\n⚠️  {result.failed_tracks} tracks could not be found on Tidal"
        )

    if dry_run:
        click.echo(
            f"\n✅ Dry run completed! {result.found_tracks} tracks "
            f"would be added to '{result.playlist_name}'."
        )
    else:
        click.echo(
            f"\n✅ Sync completed! Playlist '{result.playlist_name}' "
            f"updated with {result.added_tracks} tracks."
        )


def execute_sync_command(
    config: Config,
    playlist_name: str,
    folder_id: Optional[int],
    limit: Optional[int],
    dry_run: bool,
) -> None:
    """
    Execute the sync command with all necessary steps.
    
    This is the main orchestrator function that ties together all the
    sync command logic while keeping it separated from the Click decorators.
    """
    # Validate and sanitize playlist name
    if not playlist_name or not playlist_name.strip():
        raise click.BadParameter("Playlist name cannot be empty")
    playlist_name = playlist_name.strip()

    click.echo(f"🎵 Syncing Discogs collection to Tidal playlist: {playlist_name}")
    
    try:
        # Initialize services
        discogs_service, tidal_auth, sync_service = initialize_services(config)
        
        # Resolve folder selection (interactive or validate provided)
        resolved_folder_id = resolve_folder_selection(discogs_service, folder_id)
        
        # Display sync parameters
        display_folder_info(discogs_service, resolved_folder_id)
        display_sync_parameters(playlist_name, limit, dry_run)

        # Setup progress callbacks
        auth_progress, progress_callback = setup_progress_callbacks()

        # Authenticate services
        authenticate_services(tidal_auth)

        # Perform sync operation
        result = perform_sync(
            sync_service,
            progress_callback,
            playlist_name,
            resolved_folder_id,
        )

        # Display results
        display_sync_results(result, dry_run)

    except DiscogsToTidalError as e:
        raise click.ClickException(f"Sync failed: {e}")
    except click.ClickException:
        # Re-raise click exceptions (like BadParameter) as-is
        raise
    except KeyboardInterrupt:
        raise click.ClickException("Sync cancelled by user")
    except Exception as e:
        raise click.ClickException(f"Unexpected error: {e}")

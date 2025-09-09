"""
Discogs authentication module.
"""
import json
import logging
import os
import stat
import tempfile
import time
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from discogs_client import Client as DiscogsClient  # type: ignore[import-untyped]

from ...core.config import Config
from ...core.exceptions import AuthenticationError

logger = logging.getLogger(__name__)


class DiscogsAuthMethod(Enum):
    """Authentication methods supported by Discogs."""

    PERSONAL_TOKEN = "personal_token"
    OAUTH = "oauth"  # Future enhancement


class DiscogsAuthStatus(Enum):
    """Authentication status states for Discogs."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    EXPIRED = "expired"
    INVALID_TOKEN = "invalid_token"


class DiscogsAuth:
    """Handle Discogs authentication and session management."""

    def __init__(self, config: Config):
        self.config = config
        self._client: Optional[DiscogsClient] = None
        self._user: Any = None  # User object from discogs_client
        self.auth_timeout = 30  # 30 seconds for token validation
        self.progress_callback: Optional[Callable[[str, int], None]] = None
        self._last_auth_status = DiscogsAuthStatus.PENDING

    @property
    def client(self) -> DiscogsClient:
        """Get authenticated Discogs client."""
        if self._client is None:
            self._client = self.authenticate()
        return self._client

    @property
    def user(self) -> Any:
        """Get authenticated user info."""
        if self._user is None and self._client:
            self._authenticate_user()
        return self._user

    def set_progress_callback(self, callback: Callable[[str, int], None]) -> None:
        """Set callback for authentication progress updates."""
        self.progress_callback = callback

    def _notify_progress(self, message: str, progress: int) -> None:
        """Notify progress to callback if set."""
        if self.progress_callback:
            self.progress_callback(message, progress)

    def get_token_storage_path(self) -> Path:
        """Get secure token storage path within the project directory."""
        tokens_dir = self.config.tokens_dir
        tokens_dir.mkdir(exist_ok=True)

        # Set secure permissions (owner only)
        if os.name == "posix":
            os.chmod(tokens_dir, stat.S_IRWXU)  # 700 permissions

        return tokens_dir / "discogs_session.json"

    def save_session(
        self, session_data: dict, token_path: Optional[Path] = None
    ) -> bool:
        """Safely save Discogs session data with secure file permissions."""
        if token_path is None:
            token_path = self.get_token_storage_path()

        # Write to temporary file first, then move to avoid corruption
        temp_fd, temp_path = tempfile.mkstemp(dir=token_path.parent, suffix=".tmp")

        try:
            with os.fdopen(temp_fd, "w") as temp_file:
                json.dump(session_data, temp_file, indent=2)

            # Set secure permissions before moving
            if os.name == "posix":
                os.chmod(temp_path, stat.S_IRUSR | stat.S_IWUSR)  # 600 permissions

            # Atomic move
            os.replace(temp_path, token_path)

            logger.info(f"Discogs session data saved securely to: {token_path}")
            return True

        except Exception as e:
            # Clean up temp file on error
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                pass
            logger.error(f"Failed to save Discogs session: {e}")
            return False

    def load_session(
        self, token_path: Optional[Path] = None
    ) -> Optional[Dict[str, Any]]:
        """Load Discogs session data from secure storage."""
        if token_path is None:
            token_path = self.get_token_storage_path()

        if not token_path.exists():
            return None

        try:
            with open(token_path, "r") as f:
                session_data: Dict[str, Any] = json.load(f)

            logger.info("Discogs session data loaded successfully")
            return session_data

        except Exception as e:
            logger.warning(f"Failed to load Discogs session: {e}")
            return None

    def clear_session(self, token_path: Optional[Path] = None) -> bool:
        """Clear stored Discogs session data."""
        if token_path is None:
            token_path = self.get_token_storage_path()

        try:
            if token_path.exists():
                token_path.unlink()
                logger.info("Discogs session data cleared")
            return True
        except Exception as e:
            logger.error(f"Failed to clear Discogs session: {e}")
            return False

    def _try_existing_session(self) -> Optional[DiscogsClient]:
        """Try to use existing stored session."""
        self._notify_progress("Checking for existing Discogs session...", 10)

        session_data = self.load_session()
        if not session_data:
            return None

        token = session_data.get("personal_token")
        if not token:
            return None

        try:
            self._notify_progress("Validating stored Discogs token...", 20)

            # Test the stored token
            client = DiscogsClient("DiscogsToTidalApp/1.0", user_token=token)

            # Try to get user identity to validate token
            user = client.identity()
            if user and user.username:
                self._notify_progress("Existing Discogs session validated", 30)
                self._user = user
                logger.info(f"Using existing Discogs session for user: {user.username}")
                return client

        except Exception as e:
            logger.warning(f"Stored Discogs token is invalid: {e}")
            # Clear invalid session
            self.clear_session()

        return None

    def _prompt_for_token(self) -> Optional[str]:
        """
        Prompt user for Discogs personal token.

        Returns:
            The user-provided token or None if cancelled
        """
        try:
            print("\nDiscogs Personal Token Required:")
            print("1. Go to https://www.discogs.com/settings/developers")
            print("2. Generate a new personal access token")
            print("3. Copy and paste the token below")
            print("4. Press Enter (or Ctrl+C to cancel)")

            token = input("\nEnter your Discogs personal token: ").strip()
            if not token:
                logger.warning("No token provided by user")
                return None

            # Basic validation
            if len(token) < 10:  # Discogs tokens are typically much longer
                logger.warning("Token appears too short to be valid")
                return None

            return token

        except (KeyboardInterrupt, EOFError):
            logger.info("Token input cancelled by user")
            return None
        except Exception as e:
            logger.error(f"Error getting token from user: {e}")
            return None

    def _authenticate_personal_token(self) -> Optional[DiscogsClient]:
        """Authenticate using personal token from config."""
        if not self.config.discogs_token:
            self._notify_progress("No Discogs token configured", 40)

            # Prompt user for token
            token = self._prompt_for_token()
            if not token:
                self._last_auth_status = DiscogsAuthStatus.INVALID_TOKEN
                return None

            # Update config with the token (session will be saved separately)
            self.config.discogs_token = token

        try:
            self._notify_progress("Authenticating with Discogs personal token...", 50)

            token_preview = self.config.discogs_token[:6] + "..."
            logger.info(f"Authenticating with Discogs token: {token_preview}")

            client = DiscogsClient(
                "DiscogsToTidalApp/1.0", user_token=self.config.discogs_token
            )

            self._notify_progress("Validating Discogs credentials...", 70)

            # Validate token by getting user identity
            user = client.identity()
            if not user or not user.username:
                raise AuthenticationError("Failed to get user identity")

            self._user = user
            self._notify_progress("Discogs authentication successful", 90)

            # Save session data for future use
            session_data = {
                "personal_token": self.config.discogs_token,
                "user_id": user.id,
                "username": user.username,
                "authenticated_at": int(time.time()),
                "method": DiscogsAuthMethod.PERSONAL_TOKEN.value,
            }

            self.save_session(session_data)
            self._notify_progress("Discogs session saved", 100)

            self._last_auth_status = DiscogsAuthStatus.SUCCESS
            logger.info(f"Successfully authenticated as Discogs user: {user.username}")

            return client

        except Exception as e:
            self._last_auth_status = DiscogsAuthStatus.FAILED
            logger.error(f"Discogs authentication failed: {e}")
            raise AuthenticationError(f"Discogs authentication failed: {e}")

    def authenticate(
        self,
        method: DiscogsAuthMethod = DiscogsAuthMethod.PERSONAL_TOKEN,
        force_new: bool = False,
    ) -> DiscogsClient:
        """
        Authenticate with Discogs API.

        Args:
            method: Authentication method to use
            force_new: Force new authentication even if session exists

        Returns:
            Authenticated Discogs client
        """
        logger.info("Starting Discogs authentication...")
        self._notify_progress("Initializing Discogs authentication...", 0)

        # Try existing session unless forced
        if not force_new:
            existing_client = self._try_existing_session()
            if existing_client:
                self._client = existing_client
                return existing_client

        # Authenticate based on method
        if method == DiscogsAuthMethod.PERSONAL_TOKEN:
            client = self._authenticate_personal_token()
        else:
            raise AuthenticationError(f"Unsupported Discogs auth method: {method}")

        if not client:
            self._last_auth_status = DiscogsAuthStatus.FAILED
            raise AuthenticationError("Discogs authentication failed")

        self._client = client
        return client

    def _authenticate_user(self) -> None:
        """Get and store user information."""
        if not self._client:
            raise AuthenticationError("No authenticated Discogs client available")

        try:
            self._user = self._client.identity()
            if self._user and hasattr(self._user, "username"):
                logger.info(f"Authenticated as Discogs user: {self._user.username}")
        except Exception as e:
            raise AuthenticationError(f"Failed to get Discogs user info: {e}")

    def is_authenticated(self) -> bool:
        """Check if currently authenticated with Discogs."""
        try:
            if self._client is None or self._user is None:
                return False
            return bool(hasattr(self._user, "username") and self._user.username)
        except Exception:
            return False

    def get_auth_status(self) -> DiscogsAuthStatus:
        """Get current authentication status."""
        return self._last_auth_status

    def validate_session(self) -> bool:
        """Validate current session is still active."""
        if self._client is None or self._user is None:
            return False

        try:
            # Try to make a simple API call to validate session
            user = self._client.identity()
            return bool(user and hasattr(user, "username") and user.username)
        except Exception as e:
            logger.warning(f"Discogs session validation failed: {e}")
            return False

    def logout(self) -> bool:
        """Clear current authentication session."""
        try:
            self._client = None
            self._user = None
            self._last_auth_status = DiscogsAuthStatus.PENDING
            logger.info("Discogs logout completed")
            return True
        except Exception as e:
            logger.error(f"Error during Discogs logout: {e}")
            return False

    def get_rate_limit_info(self) -> Dict[str, Any]:
        """Get current rate limit information."""
        if not self._client:
            return {"status": "not_authenticated"}

        try:
            # Discogs rate limiting info is available in the client
            return {
                "status": "available",
                "note": "Discogs uses rate limiting - check API responses for details",
            }
        except Exception as e:
            logger.warning(f"Failed to get Discogs rate limit info: {e}")
            return {"status": "unavailable", "error": str(e)}

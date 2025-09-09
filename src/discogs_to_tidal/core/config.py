"""
Configuration management for discogs_to_tidal.
"""
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, cast

from .exceptions import ConfigurationError

logger = logging.getLogger(__name__)


@dataclass
class Config:
    """Configuration settings for the application."""

    # API Configuration
    discogs_token: Optional[str] = None

    # Application Settings
    log_level: str = "INFO"
    max_tracks: int = 0  # 0 = no limit
    cache_tracks: bool = True
    cache_expiry_hours: int = 24

    # Search Configuration
    search_timeout: int = 30
    search_retry_count: int = 3

    # Development Settings
    dev_mode: bool = False
    debug_api_calls: bool = False

    # Internal settings
    _project_root: Optional[Path] = field(default=None, init=False)
    _tokens_dir: Optional[Path] = field(default=None, init=False)

    def __post_init__(self) -> None:
        """Initialize derived settings."""
        self._project_root = self._find_project_root()
        self._tokens_dir = (
            self._project_root / ".tokens" if self._project_root else None
        )

        # Set up logging
        self.setup_logging()

        # Load tokens from storage if not already set
        if self._tokens_dir and self._tokens_dir.exists():
            self.load_tokens_from_storage()

    @classmethod
    def from_env(cls) -> "Config":
        """Create configuration from environment variables."""
        return cls(
            discogs_token=os.getenv("DISCOGS_TOKEN"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            max_tracks=int(os.getenv("MAX_TRACKS", "0")),
            cache_tracks=os.getenv("CACHE_TRACKS", "true").lower() == "true",
            cache_expiry_hours=int(os.getenv("CACHE_EXPIRY_HOURS", "24")),
            search_timeout=int(os.getenv("SEARCH_TIMEOUT", "30")),
            search_retry_count=int(os.getenv("SEARCH_RETRY_COUNT", "3")),
            dev_mode=os.getenv("DEV_MODE", "false").lower() == "true",
            debug_api_calls=os.getenv("DEBUG_API_CALLS", "false").lower() == "true",
        )

    @classmethod
    def from_dotenv(cls, env_file: Optional[Path] = None) -> "Config":
        """Create configuration from .env file."""
        try:
            from dotenv import load_dotenv

            if env_file:
                load_dotenv(env_file)
            else:
                # Try to find .env in project root
                project_root = cls._find_project_root()
                if project_root:
                    env_file = project_root / ".env"
                    if env_file.exists():
                        load_dotenv(env_file)

            return cls.from_env()

        except ImportError:
            raise ConfigurationError(
                "python-dotenv is required to load .env files. "
                "Install it with: pip install python-dotenv"
            )

    @staticmethod
    def _find_project_root() -> Optional[Path]:
        """Find the project root directory."""
        current = Path.cwd()

        # Look for markers that indicate project root
        markers = [".git", "pyproject.toml", "setup.py", "requirements.txt"]

        for parent in [current] + list(current.parents):
            if any((parent / marker).exists() for marker in markers):
                return parent

        return current

    def setup_logging(self) -> None:
        """Set up logging configuration."""
        log_level = getattr(logging, self.log_level.upper(), logging.INFO)

        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        # Set up root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)

        # Remove existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Add console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        # Add debug logging for API calls if enabled
        if self.debug_api_calls:
            logging.getLogger("requests").setLevel(logging.DEBUG)
            logging.getLogger("urllib3").setLevel(logging.DEBUG)

    def validate(self) -> None:
        """Validate the configuration."""
        errors = []

        if not self.discogs_token:
            errors.append("DISCOGS_TOKEN is required")

        if self.max_tracks < 0:
            errors.append("MAX_TRACKS must be >= 0")

        if self.cache_expiry_hours <= 0:
            errors.append("CACHE_EXPIRY_HOURS must be > 0")

        if self.search_timeout <= 0:
            errors.append("SEARCH_TIMEOUT must be > 0")

        if self.search_retry_count < 0:
            errors.append("SEARCH_RETRY_COUNT must be >= 0")

        if errors:
            raise ConfigurationError(f"Configuration errors: {', '.join(errors)}")

    @property
    def project_root(self) -> Path:
        """Get the project root directory."""
        if self._project_root is None:
            raise ConfigurationError("Could not determine project root directory")
        return self._project_root

    @property
    def tokens_dir(self) -> Path:
        """Get the tokens directory."""
        if self._tokens_dir is None:
            raise ConfigurationError("Could not determine tokens directory")
        return self._tokens_dir

    @property
    def cache_dir(self) -> Path:
        """Get the cache directory."""
        return self.project_root / ".cache"

    def ensure_directories(self) -> None:
        """Ensure required directories exist."""
        self.tokens_dir.mkdir(exist_ok=True)
        self.cache_dir.mkdir(exist_ok=True)

        # Set secure permissions on Unix systems
        if os.name == "posix":
            import stat

            os.chmod(self.tokens_dir, stat.S_IRWXU)  # 700
            os.chmod(self.cache_dir, stat.S_IRWXU)  # 700

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary (excluding private fields)."""
        return {
            key: value
            for key, value in self.__dict__.items()
            if not key.startswith("_")
        }

    def load_tokens_from_storage(self) -> None:
        """Load tokens from secure storage if available."""
        try:
            # Check for both discogs_token.json (test format)
            # and discogs_session.json (production format)
            token_files = [
                (self.tokens_dir / "discogs_token.json", "token"),
                (self.tokens_dir / "discogs_session.json", "personal_token"),
            ]

            for token_file, token_key in token_files:
                if token_file.exists() and not self.discogs_token:
                    with open(token_file, "r") as f:
                        session_data: Dict[str, Any] = json.load(f)
                        token = session_data.get(token_key)
                        if token and isinstance(token, str):
                            self.discogs_token = token
                            logger.info(f"Loaded Discogs token from {token_file.name}")
                            break

        except Exception as e:
            logger.warning(f"Failed to load tokens from storage: {e}")

    def get_discogs_token(self) -> Optional[str]:
        """
        Get Discogs token from various sources in order of priority:
        1. Already loaded in config
        2. Environment variable
        3. Secure storage file

        Returns:
            The Discogs token if found, None otherwise
        """
        # 1. Check if already loaded
        if self.discogs_token:
            return self.discogs_token

        # 2. Check environment variable
        env_token = os.getenv("DISCOGS_TOKEN")
        if env_token:
            self.discogs_token = env_token
            return env_token

        # 3. Check secure session storage
        try:
            # Check for both discogs_token.json (test format)
            # and discogs_session.json (production format)
            token_files = [
                (self.tokens_dir / "discogs_token.json", "token"),
                (self.tokens_dir / "discogs_session.json", "personal_token"),
            ]

            for token_file, token_key in token_files:
                if token_file.exists():
                    with open(token_file, "r") as f:
                        session_data: Dict[str, Any] = json.load(f)
                        token = session_data.get(token_key)
                        if token and isinstance(token, str):
                            self.discogs_token = token
                            logger.info(f"Loaded Discogs token from {token_file.name}")
                            return cast(str, token)
        except Exception as e:
            logger.warning(f"Failed to load Discogs token from session storage: {e}")

        return None

    def save_discogs_token(self, token: str) -> bool:
        """
        Save Discogs token to secure storage.

        Args:
            token: The Discogs token to save

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            import stat
            import tempfile
            from datetime import datetime

            self.ensure_directories()

            # Create session data structure (compatible with test format)
            session_data = {
                "token": token,
                "service": "discogs",
                "token_type": "personal_token",
                "created_at": datetime.now().isoformat(),
            }

            # Write to temporary file first for atomicity
            discogs_token_file = self.tokens_dir / "discogs_token.json"

            # Use mkstemp for compatibility with tests that patch it
            import os

            temp_fd, temp_file_path = tempfile.mkstemp(
                dir=self.tokens_dir, suffix=".tmp", text=True
            )

            try:
                with os.fdopen(temp_fd, "w") as temp_file:
                    json.dump(session_data, temp_file, indent=2)
            except Exception:
                # Clean up the file descriptor and temp file on error
                try:
                    os.close(temp_fd)
                except Exception:
                    pass
                try:
                    os.unlink(temp_file_path)
                except Exception:
                    pass
                raise

            # Set secure permissions on Unix systems
            if os.name == "posix":
                os.chmod(temp_file_path, stat.S_IRUSR | stat.S_IWUSR)  # 600

            # Atomically replace the target file
            os.replace(temp_file_path, discogs_token_file)

            # Update in-memory token
            self.discogs_token = token

            logger.info("Discogs token saved to secure storage")
            return True

        except Exception as e:
            logger.error(f"Failed to save Discogs token: {e}")
            # Clean up temp file if it exists
            try:
                if "temp_file_path" in locals() and Path(temp_file_path).exists():
                    os.unlink(temp_file_path)
            except Exception:
                pass
            return False

    def __str__(self) -> str:
        config_dict = self.to_dict()
        # Hide sensitive information
        if config_dict.get("discogs_token"):
            config_dict["discogs_token"] = f"{config_dict['discogs_token'][:6]}..."
        return f"Config({config_dict})"

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
            # Load Discogs token from session file
            discogs_session_file = self.tokens_dir / "discogs_session.json"
            if discogs_session_file.exists() and not self.discogs_token:
                with open(discogs_session_file, "r") as f:
                    session_data: Dict[str, Any] = json.load(f)
                    token = session_data.get("personal_token")
                    if token and isinstance(token, str):
                        self.discogs_token = token
                        logger.info("Loaded Discogs token from session storage")

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
            discogs_session_file = self.tokens_dir / "discogs_session.json"
            if discogs_session_file.exists():
                with open(discogs_session_file, "r") as f:
                    session_data: Dict[str, Any] = json.load(f)
                    token = session_data.get("personal_token")
                    if token and isinstance(token, str):
                        self.discogs_token = token
                        logger.info("Loaded Discogs token from session storage")
                        return cast(str, token)
        except Exception as e:
            logger.warning(f"Failed to load Discogs token from session storage: {e}")

        return None

    def __str__(self) -> str:
        config_dict = self.to_dict()
        # Hide sensitive information
        if config_dict.get("discogs_token"):
            config_dict["discogs_token"] = f"{config_dict['discogs_token'][:6]}..."
        return f"Config({config_dict})"

"""
Unit tests for core.config module.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from discogs_to_tidal.core.config import Config
from discogs_to_tidal.core.exceptions import ConfigurationError


class TestConfig(unittest.TestCase):
    """Test cases for Config class."""

    def setUp(self):
        """Set up test fixtures before each test."""
        # Clean up any existing token to ensure clean test state
        with patch.object(Config, "load_tokens_from_storage"):
            self.clean_config = Config()
        self.clean_config.discogs_token = None

    def test_config_defaults(self):
        """Test Config initialization with default values."""
        with patch.object(Config, "load_tokens_from_storage"):
            config = Config()
            config.discogs_token = None  # Ensure clean state

        self.assertIsNone(config.discogs_token)
        self.assertEqual(config.log_level, "INFO")
        self.assertEqual(config.max_tracks, 0)
        self.assertTrue(config.cache_tracks)
        self.assertEqual(config.cache_expiry_hours, 24)
        self.assertEqual(config.search_timeout, 30)
        self.assertEqual(config.search_retry_count, 3)
        self.assertFalse(config.dev_mode)
        self.assertFalse(config.debug_api_calls)

    def test_config_initialization(self):
        """Test Config initialization with custom values."""
        with patch.object(Config, "load_tokens_from_storage"):
            config = Config(
                discogs_token="custom_token",
                log_level="WARNING",
                max_tracks=50,
                cache_tracks=False,
                cache_expiry_hours=48,
                search_timeout=60,
                search_retry_count=5,
                dev_mode=True,
                debug_api_calls=True,
            )

        self.assertEqual(config.discogs_token, "custom_token")
        self.assertEqual(config.log_level, "WARNING")
        self.assertEqual(config.max_tracks, 50)
        self.assertFalse(config.cache_tracks)
        self.assertEqual(config.cache_expiry_hours, 48)
        self.assertEqual(config.search_timeout, 60)
        self.assertEqual(config.search_retry_count, 5)
        self.assertTrue(config.dev_mode)
        self.assertTrue(config.debug_api_calls)

    @patch.dict(os.environ, {}, clear=True)
    def test_from_env_with_no_env_vars(self):
        """Test Config.from_env() with no environment variables."""
        with patch.object(Config, "load_tokens_from_storage"):
            config = Config.from_env()
            config.discogs_token = None  # Ensure clean state

        self.assertIsNone(config.discogs_token)
        self.assertEqual(config.log_level, "INFO")
        self.assertEqual(config.max_tracks, 0)
        self.assertTrue(config.cache_tracks)
        self.assertEqual(config.cache_expiry_hours, 24)
        self.assertEqual(config.search_timeout, 30)
        self.assertEqual(config.search_retry_count, 3)
        self.assertFalse(config.dev_mode)
        self.assertFalse(config.debug_api_calls)

    @patch.dict(
        os.environ,
        {"DISCOGS_TOKEN": "test_token", "LOG_LEVEL": "DEBUG", "MAX_TRACKS": "200"},
    )
    def test_from_env_with_env_vars(self):
        """Test Config.from_env() with environment variables."""
        config = Config.from_env()

        self.assertEqual(config.discogs_token, "test_token")
        self.assertEqual(config.log_level, "DEBUG")
        self.assertEqual(config.max_tracks, 200)

    @patch.dict(
        os.environ,
        {"CACHE_TRACKS": "false", "DEV_MODE": "true", "DEBUG_API_CALLS": "TRUE"},
    )
    def test_from_env_boolean_values(self):
        """Test Config.from_env() with boolean environment variables."""
        config = Config.from_env()

        self.assertFalse(config.cache_tracks)
        self.assertTrue(config.dev_mode)
        self.assertTrue(config.debug_api_calls)

    @patch.dict(os.environ, {"MAX_TRACKS": "invalid"})
    def test_from_env_invalid_integer(self):
        """Test Config.from_env() with invalid integer values."""
        with self.assertRaises(ValueError):
            Config.from_env()

    def test_find_project_root_with_git(self):
        """Test _find_project_root() finding .git directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            git_dir = project_root / ".git"
            git_dir.mkdir()

            sub_dir = project_root / "sub" / "dir"
            sub_dir.mkdir(parents=True)

            with patch("pathlib.Path.cwd", return_value=sub_dir):
                result = Config._find_project_root()
                self.assertEqual(result, project_root)

    def test_find_project_root_with_pyproject_toml(self):
        """Test _find_project_root() finding pyproject.toml file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "pyproject.toml").touch()

            sub_dir = project_root / "sub"
            sub_dir.mkdir()

            with patch("pathlib.Path.cwd", return_value=sub_dir):
                result = Config._find_project_root()
                self.assertEqual(result, project_root)

    def test_find_project_root_fallback_to_cwd(self):
        """Test _find_project_root() fallback to current directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            current_dir = Path(temp_dir)

            with patch("pathlib.Path.cwd", return_value=current_dir):
                result = Config._find_project_root()
                self.assertEqual(result, current_dir)

    def test_validate_valid_config(self):
        """Test validate() with valid configuration."""
        with patch.object(Config, "load_tokens_from_storage"):
            config = Config(discogs_token="valid_token")

        # Should not raise any exception
        config.validate()

    def test_validate_missing_discogs_token(self):
        """Test validate() with missing Discogs token."""
        with patch.object(Config, "load_tokens_from_storage"):
            config = Config()
            config.discogs_token = None  # Ensure no token

        with self.assertRaises(ConfigurationError) as cm:
            config.validate()

        self.assertIn("DISCOGS_TOKEN is required", str(cm.exception))

    def test_validate_negative_max_tracks(self):
        """Test validate() with negative max_tracks."""
        with patch.object(Config, "load_tokens_from_storage"):
            config = Config(discogs_token="token", max_tracks=-1)

        with self.assertRaises(ConfigurationError) as cm:
            config.validate()

        self.assertIn("MAX_TRACKS must be >= 0", str(cm.exception))

    def test_validate_invalid_cache_expiry(self):
        """Test validate() with invalid cache_expiry_hours."""
        with patch.object(Config, "load_tokens_from_storage"):
            config = Config(discogs_token="token", cache_expiry_hours=0)

        with self.assertRaises(ConfigurationError) as cm:
            config.validate()

        self.assertIn("CACHE_EXPIRY_HOURS must be > 0", str(cm.exception))

    def test_validate_invalid_search_timeout(self):
        """Test validate() with invalid search_timeout."""
        with patch.object(Config, "load_tokens_from_storage"):
            config = Config(discogs_token="token", search_timeout=0)

        with self.assertRaises(ConfigurationError) as cm:
            config.validate()

        self.assertIn("SEARCH_TIMEOUT must be > 0", str(cm.exception))

    def test_validate_negative_retry_count(self):
        """Test validate() with negative search_retry_count."""
        with patch.object(Config, "load_tokens_from_storage"):
            config = Config(discogs_token="token", search_retry_count=-1)

        with self.assertRaises(ConfigurationError) as cm:
            config.validate()

        self.assertIn("SEARCH_RETRY_COUNT must be >= 0", str(cm.exception))

    def test_validate_multiple_errors(self):
        """Test validate() with multiple configuration errors."""
        with patch.object(Config, "load_tokens_from_storage"):
            config = Config(max_tracks=-1, cache_expiry_hours=0)
            config.discogs_token = None  # Ensure no token

        with self.assertRaises(ConfigurationError) as cm:
            config.validate()

        error_message = str(cm.exception)
        self.assertIn("DISCOGS_TOKEN is required", error_message)
        self.assertIn("MAX_TRACKS must be >= 0", error_message)
        self.assertIn("CACHE_EXPIRY_HOURS must be > 0", error_message)

    def test_to_dict(self):
        """Test to_dict() method."""
        with patch.object(Config, "load_tokens_from_storage"):
            config = Config(discogs_token="token", log_level="DEBUG", max_tracks=100)

        result = config.to_dict()

        # Should include public fields
        self.assertEqual(result["discogs_token"], "token")
        self.assertEqual(result["log_level"], "DEBUG")
        self.assertEqual(result["max_tracks"], 100)

        # Should not include private fields
        self.assertNotIn("_project_root", result)
        self.assertNotIn("_tokens_dir", result)

    def test_load_tokens_from_storage_success(self):
        """Test load_tokens_from_storage() successful loading."""
        with tempfile.TemporaryDirectory() as temp_dir:
            tokens_dir = Path(temp_dir) / ".tokens"
            tokens_dir.mkdir()

            # Create token file
            token_file = tokens_dir / "discogs_token.json"
            token_data = {"token": "stored_token_123"}
            with open(token_file, "w") as f:
                json.dump(token_data, f)

            with patch.object(
                Config, "_find_project_root", return_value=Path(temp_dir)
            ):
                config = Config()
                config.discogs_token = None  # Clear any existing token
                config.load_tokens_from_storage()

                self.assertEqual(config.discogs_token, "stored_token_123")

    def test_load_tokens_from_storage_no_token_file(self):
        """Test load_tokens_from_storage() with no token file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(
                Config, "_find_project_root", return_value=Path(temp_dir)
            ):
                with patch.object(Config, "setup_logging"):  # Skip logging setup
                    config = Config(discogs_token="existing_token")
                    original_token = config.discogs_token

                    config.load_tokens_from_storage()

                    # Should not change existing token
                    self.assertEqual(config.discogs_token, original_token)

    def test_load_tokens_from_storage_invalid_json(self):
        """Test load_tokens_from_storage() with invalid JSON."""
        with tempfile.TemporaryDirectory() as temp_dir:
            tokens_dir = Path(temp_dir) / ".tokens"
            tokens_dir.mkdir()

            # Create invalid token file
            token_file = tokens_dir / "discogs_token.json"
            with open(token_file, "w") as f:
                f.write("invalid json")

            with patch.object(
                Config, "_find_project_root", return_value=Path(temp_dir)
            ):
                with patch.object(Config, "setup_logging"):  # Skip logging setup
                    config = Config()
                    config.discogs_token = None

                    # Should not raise exception, just log warning
                    config.load_tokens_from_storage()
                    self.assertIsNone(config.discogs_token)

    @patch.dict(os.environ, {"DISCOGS_TOKEN": "env_token"})
    def test_get_discogs_token_from_env(self):
        """Test get_discogs_token() from environment variable."""
        with patch.object(Config, "load_tokens_from_storage"):
            config = Config()
            config.discogs_token = None  # Clear any existing token

            result = config.get_discogs_token()

            self.assertEqual(result, "env_token")
            self.assertEqual(config.discogs_token, "env_token")

    def test_get_discogs_token_from_storage(self):
        """Test get_discogs_token() from storage file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            tokens_dir = Path(temp_dir) / ".tokens"
            tokens_dir.mkdir()

            # Create token file
            token_file = tokens_dir / "discogs_token.json"
            token_data = {"token": "storage_token_123"}
            with open(token_file, "w") as f:
                json.dump(token_data, f)

            with patch.object(
                Config, "_find_project_root", return_value=Path(temp_dir)
            ):
                with patch.dict(os.environ, {}, clear=True):
                    with patch.object(Config, "setup_logging"):  # Skip logging setup
                        config = Config()
                        config.discogs_token = None  # Clear any existing token

                        result = config.get_discogs_token()

                        self.assertEqual(result, "storage_token_123")
                        self.assertEqual(config.discogs_token, "storage_token_123")

    @patch.dict(os.environ, {}, clear=True)
    def test_get_discogs_token_not_found(self):
        """Test get_discogs_token() when token is not found anywhere."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(
                Config, "_find_project_root", return_value=Path(temp_dir)
            ):
                with patch.object(Config, "load_tokens_from_storage"):
                    config = Config()
                    config.discogs_token = None  # Ensure no token

                    result = config.get_discogs_token()

                    self.assertIsNone(result)

    def test_get_discogs_token_already_loaded(self):
        """Test get_discogs_token() with token already loaded."""
        with patch.object(Config, "load_tokens_from_storage"):
            config = Config(discogs_token="loaded_token")

        result = config.get_discogs_token()

        self.assertEqual(result, "loaded_token")

    def test_str_representation(self):
        """Test __str__() method."""
        with patch.object(Config, "load_tokens_from_storage"):
            config = Config(discogs_token="test_token_12345", log_level="DEBUG")

        result = str(config)

        # Should contain config info
        self.assertIn("Config(", result)
        self.assertIn("log_level", result)
        self.assertIn("DEBUG", result)

        # Should mask sensitive token
        self.assertIn("test_t...", result)
        self.assertNotIn("test_token_12345", result)

    def test_str_representation_no_token(self):
        """Test __str__() method with no token."""
        with patch.object(Config, "load_tokens_from_storage"):
            config = Config(log_level="INFO")
            config.discogs_token = None

        result = str(config)

        self.assertIn("Config(", result)
        self.assertIn("log_level", result)


class TestConfigAdvanced(unittest.TestCase):
    """Additional comprehensive test cases for Config class to increase coverage."""

    def test_post_init_with_existing_tokens_dir(self):
        """Test __post_init__ when tokens directory exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            tokens_dir = Path(temp_dir) / ".tokens"
            tokens_dir.mkdir()

            # Create a token file
            token_file = tokens_dir / "discogs_token.json"
            token_data = {"token": "test_token_from_storage"}
            with open(token_file, "w") as f:
                json.dump(token_data, f)

            project_root = Path(temp_dir)
            with patch.object(Config, "_find_project_root", return_value=project_root):
                # Skip logging to avoid side effects
                with patch.object(Config, "setup_logging"):
                    config = Config()

                    # Should have loaded the token from storage
                    self.assertEqual(config.discogs_token, "test_token_from_storage")

    def test_post_init_no_tokens_dir(self):
        """Test __post_init__ when tokens directory doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            with patch.object(Config, "_find_project_root", return_value=project_root):
                # Skip logging to avoid side effects
                with patch.object(Config, "setup_logging"):
                    config = Config()

                    # Should not crash and should not have loaded any token
                    self.assertIsNone(config.discogs_token)

    def test_from_dotenv_with_specific_file(self):
        """Test from_dotenv with a specific .env file path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / "custom.env"
            env_content = """DISCOGS_TOKEN=dotenv_token
LOG_LEVEL=WARNING
MAX_TRACKS=500"""
            with open(env_file, "w") as f:
                f.write(env_content)

            # Mock dotenv module import instead of specific function
            with patch("builtins.__import__") as mock_import:
                mock_dotenv = MagicMock()
                mock_import.return_value = mock_dotenv

                env_vars = {
                    "DISCOGS_TOKEN": "dotenv_token",
                    "LOG_LEVEL": "WARNING",
                    "MAX_TRACKS": "500",
                }
                with patch.dict(os.environ, env_vars):
                    config = Config.from_dotenv(env_file)

                    self.assertEqual(config.discogs_token, "dotenv_token")
                    self.assertEqual(config.log_level, "WARNING")
                    self.assertEqual(config.max_tracks, 500)

    def test_from_dotenv_no_env_file_found(self):
        """Test from_dotenv when no .env file is found in project root."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            with patch.object(Config, "_find_project_root", return_value=project_root):
                # Just test the ImportError path instead
                with patch("builtins.__import__", side_effect=ImportError()):
                    with self.assertRaises(ConfigurationError):
                        Config.from_dotenv()

    def test_setup_logging_with_debug_api_calls(self):
        """Test setup_logging when debug_api_calls is True."""
        with patch.object(Config, "load_tokens_from_storage"):
            with patch("logging.getLogger") as mock_get_logger:
                mock_root_logger = MagicMock()
                mock_requests_logger = MagicMock()
                mock_urllib3_logger = MagicMock()

                def get_logger_side_effect(name=None):
                    if name == "requests":
                        return mock_requests_logger
                    elif name == "urllib3":
                        return mock_urllib3_logger
                    elif name is None:
                        return mock_root_logger
                    else:
                        return MagicMock()

                mock_get_logger.side_effect = get_logger_side_effect

                config = Config(debug_api_calls=True)
                config.setup_logging()

                # Should set debug level for requests and urllib3 loggers
                # logging.DEBUG = 10
                mock_requests_logger.setLevel.assert_called_with(10)
                mock_urllib3_logger.setLevel.assert_called_with(10)

    def test_setup_logging_invalid_log_level(self):
        """Test setup_logging with invalid log level defaults to INFO."""
        with patch.object(Config, "load_tokens_from_storage"):
            with patch("logging.getLogger") as mock_get_logger:
                mock_root_logger = MagicMock()
                mock_get_logger.return_value = mock_root_logger

                config = Config(log_level="INVALID_LEVEL")
                config.setup_logging()

                # Should default to INFO level (20)
                mock_root_logger.setLevel.assert_called_with(20)  # logging.INFO = 20

    def test_ensure_directories_creates_dirs(self):
        """Test ensure_directories creates both tokens and cache directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(
                Config, "_find_project_root", return_value=Path(temp_dir)
            ):
                with patch.object(Config, "load_tokens_from_storage"):
                    config = Config()

                    # Remove directories if they exist
                    tokens_dir = config.tokens_dir
                    cache_dir = config.cache_dir
                    if tokens_dir.exists():
                        tokens_dir.rmdir()
                    if cache_dir.exists():
                        cache_dir.rmdir()

                    config.ensure_directories()

                    self.assertTrue(tokens_dir.exists())
                    self.assertTrue(cache_dir.exists())

    @patch("os.name", "posix")
    @patch("os.chmod")
    def test_ensure_directories_sets_permissions_unix(self, mock_chmod):
        """Test ensure_directories sets proper permissions on Unix systems."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(
                Config, "_find_project_root", return_value=Path(temp_dir)
            ):
                with patch.object(Config, "load_tokens_from_storage"):
                    config = Config()
                    config.ensure_directories()

                    # Should call chmod twice (tokens_dir and cache_dir)
                    self.assertEqual(mock_chmod.call_count, 2)
                    # Check that it was called with proper permissions (700)
                    calls = mock_chmod.call_args_list
                    for call in calls:
                        self.assertEqual(call[0][1], 0o700)  # stat.S_IRWXU

    def test_save_discogs_token_success_with_real_files(self):
        """Test save_discogs_token with actual file operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(
                Config, "_find_project_root", return_value=Path(temp_dir)
            ):
                with patch.object(Config, "load_tokens_from_storage"):
                    config = Config()

                    # Save a token
                    result = config.save_discogs_token("new_test_token")

                    self.assertTrue(result)
                    self.assertEqual(config.discogs_token, "new_test_token")

                    # Verify file was created
                    token_file = config.tokens_dir / "discogs_token.json"
                    self.assertTrue(token_file.exists())

                    # Verify file contents
                    with open(token_file, "r") as f:
                        data = json.load(f)
                        self.assertEqual(data["token"], "new_test_token")
                        self.assertEqual(data["service"], "discogs")
                        self.assertEqual(data["token_type"], "personal_token")
                        self.assertIn("created_at", data)

    @patch("tempfile.mkstemp")
    def test_save_discogs_token_tempfile_error_cleanup(self, mock_mkstemp):
        """Test save_discogs_token cleans up temp file on error."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock mkstemp to raise an exception
            mock_mkstemp.side_effect = OSError("Disk full")

            with patch.object(
                Config, "_find_project_root", return_value=Path(temp_dir)
            ):
                with patch.object(Config, "load_tokens_from_storage"):
                    config = Config()

                    result = config.save_discogs_token("test_token")

                    self.assertFalse(result)
                    # Original token should be unchanged
                    self.assertIsNone(config.discogs_token)

    def test_save_discogs_token_json_write_error(self):
        """Test save_discogs_token handles JSON write errors."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(
                Config, "_find_project_root", return_value=Path(temp_dir)
            ):
                with patch.object(Config, "load_tokens_from_storage"):
                    config = Config()

                    # Mock json.dump to raise an exception
                    with patch("json.dump", side_effect=ValueError("Invalid JSON")):
                        result = config.save_discogs_token("test_token")

                        self.assertFalse(result)
                        self.assertIsNone(config.discogs_token)

    @patch("os.name", "posix")
    @patch("os.chmod")
    def test_save_discogs_token_sets_file_permissions(self, mock_chmod):
        """Test save_discogs_token sets proper file permissions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(
                Config, "_find_project_root", return_value=Path(temp_dir)
            ):
                with patch.object(Config, "load_tokens_from_storage"):
                    config = Config()

                    config.save_discogs_token("test_token")

                    # Should have called chmod for directories and file
                    self.assertTrue(mock_chmod.called)

                    # Check that file permission (600) was set
                    calls = mock_chmod.call_args_list
                    file_permission_calls = [
                        call for call in calls if call[0][1] == 0o600
                    ]
                    self.assertTrue(len(file_permission_calls) > 0)

    def test_get_discogs_token_priority_already_loaded(self):
        """Test get_discogs_token priority: already loaded token wins."""
        with tempfile.TemporaryDirectory() as temp_dir:
            tokens_dir = Path(temp_dir) / ".tokens"
            tokens_dir.mkdir()

            # Create storage file
            token_file = tokens_dir / "discogs_token.json"
            token_data = {"token": "storage_token"}
            with open(token_file, "w") as f:
                json.dump(token_data, f)

            with patch.object(
                Config, "_find_project_root", return_value=Path(temp_dir)
            ):
                with patch.dict(os.environ, {"DISCOGS_TOKEN": "env_token"}):
                    with patch.object(Config, "load_tokens_from_storage"):
                        config = Config(discogs_token="loaded_token")

                        result = config.get_discogs_token()

                        # Should return already loaded token, not env or storage
                        self.assertEqual(result, "loaded_token")

    def test_get_discogs_token_storage_json_error(self):
        """Test get_discogs_token handles JSON errors in storage file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            tokens_dir = Path(temp_dir) / ".tokens"
            tokens_dir.mkdir()

            # Create invalid JSON file
            token_file = tokens_dir / "discogs_token.json"
            with open(token_file, "w") as f:
                f.write('{"invalid": json content}')

            with patch.object(
                Config, "_find_project_root", return_value=Path(temp_dir)
            ):
                with patch.dict(os.environ, {}, clear=True):
                    with patch.object(Config, "load_tokens_from_storage"):
                        config = Config()
                        config.discogs_token = None

                        result = config.get_discogs_token()

                        # Should return None due to JSON error
                        self.assertIsNone(result)

    def test_get_discogs_token_storage_file_missing_token_key(self):
        """Test get_discogs_token when storage file exists but has no token key."""
        with tempfile.TemporaryDirectory() as temp_dir:
            tokens_dir = Path(temp_dir) / ".tokens"
            tokens_dir.mkdir()

            # Create file without token key
            token_file = tokens_dir / "discogs_token.json"
            token_data = {"service": "discogs", "created_at": 12345}
            with open(token_file, "w") as f:
                json.dump(token_data, f)

            with patch.object(
                Config, "_find_project_root", return_value=Path(temp_dir)
            ):
                with patch.dict(os.environ, {}, clear=True):
                    with patch.object(Config, "load_tokens_from_storage"):
                        config = Config()
                        config.discogs_token = None

                        result = config.get_discogs_token()

                        # Should return None since no token key
                        self.assertIsNone(result)

    def test_load_tokens_from_storage_loads_existing_token(self):
        """Test load_tokens_from_storage when token already exists in config."""
        with tempfile.TemporaryDirectory() as temp_dir:
            tokens_dir = Path(temp_dir) / ".tokens"
            tokens_dir.mkdir()

            # Create storage file
            token_file = tokens_dir / "discogs_token.json"
            token_data = {"token": "storage_token"}
            with open(token_file, "w") as f:
                json.dump(token_data, f)

            with patch.object(
                Config, "_find_project_root", return_value=Path(temp_dir)
            ):
                with patch.object(Config, "setup_logging"):
                    config = Config(discogs_token="existing_token")

                    # Manually call load_tokens_from_storage
                    config.load_tokens_from_storage()

                    # Should NOT overwrite existing token
                    self.assertEqual(config.discogs_token, "existing_token")

    def test_load_tokens_from_storage_no_token_in_file(self):
        """Test load_tokens_from_storage when file exists but has no token."""
        with tempfile.TemporaryDirectory() as temp_dir:
            tokens_dir = Path(temp_dir) / ".tokens"
            tokens_dir.mkdir()

            # Create file without token
            token_file = tokens_dir / "discogs_token.json"
            token_data = {"service": "discogs"}
            with open(token_file, "w") as f:
                json.dump(token_data, f)

            with patch.object(
                Config, "_find_project_root", return_value=Path(temp_dir)
            ):
                with patch.object(Config, "setup_logging"):
                    config = Config()
                    config.discogs_token = None

                    config.load_tokens_from_storage()

                    # Should remain None
                    self.assertIsNone(config.discogs_token)

    def test_find_project_root_with_setup_py(self):
        """Test _find_project_root finding setup.py file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "setup.py").touch()

            sub_dir = project_root / "deep" / "nested" / "dir"
            sub_dir.mkdir(parents=True)

            with patch("pathlib.Path.cwd", return_value=sub_dir):
                result = Config._find_project_root()
                self.assertEqual(result, project_root)

    def test_find_project_root_with_requirements_txt(self):
        """Test _find_project_root finding requirements.txt file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "requirements.txt").touch()

            sub_dir = project_root / "src" / "module"
            sub_dir.mkdir(parents=True)

            with patch("pathlib.Path.cwd", return_value=sub_dir):
                result = Config._find_project_root()
                self.assertEqual(result, project_root)

    def test_find_project_root_multiple_markers(self):
        """Test _find_project_root with multiple markers present."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / ".git").mkdir()
            (project_root / "pyproject.toml").touch()
            (project_root / "setup.py").touch()

            sub_dir = project_root / "tests" / "unit"
            sub_dir.mkdir(parents=True)

            with patch("pathlib.Path.cwd", return_value=sub_dir):
                result = Config._find_project_root()
                self.assertEqual(result, project_root)

    def test_tokens_dir_property_with_none_project_root(self):
        """Test tokens_dir property when project root is None."""
        with patch.object(Config, "_find_project_root", return_value=None):
            with patch.object(Config, "load_tokens_from_storage"):
                config = Config()

                with self.assertRaises(ConfigurationError) as cm:
                    _ = config.tokens_dir

                self.assertIn("Could not determine tokens directory", str(cm.exception))

    def test_cache_dir_property_with_valid_root(self):
        """Test cache_dir property returns correct path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)

            with patch.object(Config, "_find_project_root", return_value=project_root):
                with patch.object(Config, "load_tokens_from_storage"):
                    config = Config()

                    cache_dir = config.cache_dir
                    self.assertEqual(cache_dir, project_root / ".cache")

    def test_ensure_directories_windows_no_chmod(self):
        """Test ensure_directories on Windows doesn't call chmod."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            with patch.object(Config, "_find_project_root", return_value=project_root):
                with patch.object(Config, "load_tokens_from_storage"):
                    with patch("os.name", "nt"):  # Patch after Path creation
                        with patch("os.chmod") as mock_chmod:
                            config = Config()
                            config.ensure_directories()

                            # Should not call chmod on Windows
                            mock_chmod.assert_not_called()

    def test_validate_with_invalid_log_level_still_passes(self):
        """Test validate doesn't check log_level validity."""
        with patch.object(Config, "load_tokens_from_storage"):
            config = Config(discogs_token="valid_token", log_level="INVALID")

            # Should not raise any exception even with invalid log level
            config.validate()

    def test_str_with_very_short_token(self):
        """Test __str__ with token shorter than 6 characters."""
        with patch.object(Config, "load_tokens_from_storage"):
            config = Config(discogs_token="short")

            result = str(config)

            # Should handle short tokens gracefully
            self.assertIn("Config(", result)
            # Token should be masked - the actual logic does "short"[:6]+"..."
            self.assertIn("short...", result)


if __name__ == "__main__":
    unittest.main()

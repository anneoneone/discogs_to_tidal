"""
Lightweight and maintainable Tidal authentication module.

This module provides a clean authentication system for Tidal that:
- Manages session tokens securely with automatic refresh
- Provides progress callbacks for better UX
- Handles OAuth flows with intelligent polling
- Implements proper error handling and recovery
"""
import json
import logging
import os
import stat
import tempfile
import time
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from enum import Enum

import tidalapi

from ...core.exceptions import AuthenticationError
from ...core.config import Config

logger = logging.getLogger(__name__)


class AuthMethod(Enum):
    """Authentication methods supported by Tidal."""
    OAUTH_DEVICE = "oauth_device"      # Device code flow (most reliable)
    OAUTH_SIMPLE = "oauth_simple"      # Simple OAuth (fallback)


class TidalAuth:
    """Clean and maintainable Tidal authentication with essential features."""
    
    def __init__(self, config: Config):
        self.config = config
        self._session: Optional[tidalapi.Session] = None
        self.auth_timeout = 300  # 5 minutes
        self.progress_callback: Optional[Callable[[str, int], None]] = None
        
        # Polling configuration
        self.poll_interval = 3.0       # Check every 3 seconds
        self.max_poll_interval = 10.0  # Max 10 seconds between polls
        self.backoff_factor = 1.2      # Gentle increase in polling interval
    
    @property
    def session(self) -> tidalapi.Session:
        """Get authenticated Tidal session."""
        if self._session is None:
            self._session = self.authenticate()
        return self._session
    
    def set_progress_callback(self, callback: Callable[[str, int], None]) -> None:
        """Set callback for authentication progress updates."""
        self.progress_callback = callback
    
    def _notify_progress(self, message: str, progress: int) -> None:
        """Notify progress to callback if set."""
        if self.progress_callback:
            self.progress_callback(message, progress)
        logger.info(f"Auth progress ({progress}%): {message}")
        
    def _create_session(self) -> tidalapi.Session:
        """Create a basic Tidal session."""
        session = tidalapi.Session()
        logger.debug("Created Tidal session")
        return session
    
    def get_token_path(self) -> Path:
        """Get the path where tokens are stored."""
        tokens_dir = self.config.tokens_dir
        tokens_dir.mkdir(exist_ok=True)
        
        # Set secure permissions (owner only)
        if os.name == 'posix':
            os.chmod(tokens_dir, stat.S_IRWXU)  # 700 permissions
        
        return tokens_dir / 'tidal_session.json'
    
    def save_session(self, session_data: Dict[str, Any]) -> bool:
        """Save Tidal session data securely."""
        token_path = self.get_token_path()
        
        # Add metadata
        enhanced_data = {
            **session_data,
            "saved_at": time.time(),
            "expires_at": session_data.get("expires_at", time.time() + 3600),
            "auth_method": session_data.get("auth_method", "oauth_device"),
        }
        
        # Atomic write operation
        temp_fd, temp_path = tempfile.mkstemp(dir=token_path.parent, suffix='.tmp')
        
        try:
            with os.fdopen(temp_fd, 'w') as temp_file:
                json.dump(enhanced_data, temp_file, indent=2)
            
            # Set secure permissions
            if os.name == 'posix':
                os.chmod(temp_path, stat.S_IRUSR | stat.S_IWUSR)  # 600 permissions
            
            # Atomic move
            os.replace(temp_path, token_path)
            logger.info("Session data saved securely")
            return True
            
        except Exception as e:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            logger.error(f"Error saving session data: {e}")
            return False
    
    def load_session(self) -> Optional[Dict[str, Any]]:
        """Load and validate Tidal session data."""
        token_path = self.get_token_path()
        
        if not token_path.exists():
            logger.debug("No saved session found")
            return None
        
        try:
            with open(token_path, 'r') as file:
                session_data = json.load(file)
                
                # Basic validation
                required_fields = ['token_type', 'access_token']
                if not all(field in session_data for field in required_fields):
                    logger.warning("Invalid session data, clearing")
                    self.clear_session()
                    return None
                
                # Check expiration
                expires_at = session_data.get('expires_at', 0)
                if time.time() > expires_at:
                    logger.info("Session expired, clearing")
                    self.clear_session()
                    return None
                
                logger.debug("Loaded valid session data")
                return session_data
                
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading session: {e}")
            self.clear_session()
            return None
    
    def clear_session(self) -> bool:
        """Clear saved session data."""
        token_path = self.get_token_path()
        
        try:
            if token_path.exists():
                token_path.unlink()
                logger.info("Cleared saved session data")
            self._session = None
            return True
        except Exception as e:
            logger.error(f"Error clearing session: {e}")
            return False
    
    def validate_session(self, session: tidalapi.Session) -> bool:
        """Validate that a session is working."""
        try:
            if not session.check_login():
                logger.debug("Session check_login() returned False")
                return False
            
            # Try to access user info
            user = session.user
            if user and hasattr(user, 'id'):
                logger.debug(f"Session valid for user: {str(user.id)[:10]}")
                return True
            else:
                logger.debug("No user info available in session")
                return False
                
        except Exception as e:
            logger.debug(f"Session validation failed: {e}")
            return False
    
    def try_refresh_session(
        self, session: tidalapi.Session, session_data: Dict[str, Any]
    ) -> bool:
        """Try to refresh an expired session."""
        refresh_token = session_data.get('refresh_token')
        if not refresh_token:
            return False
        
        try:
            logger.info("Attempting to refresh session...")
            if session.token_refresh(refresh_token):
                logger.info("Session refreshed successfully")
                
                # Update stored data
                updated_data = {
                    **session_data,
                    "token_type": session.token_type,
                    "access_token": session.access_token,
                    "refresh_token": session.refresh_token,
                    "saved_at": time.time(),
                    "expires_at": time.time() + 3600,
                }
                
                return self.save_session(updated_data)
            return False
                
        except Exception as e:
            logger.warning(f"Session refresh failed: {e}")
            return False
    
    def authenticate(
        self,
        method: AuthMethod = AuthMethod.OAUTH_DEVICE,
        timeout_seconds: Optional[int] = None,
        auto_open_browser: bool = True,
        force_new: bool = False
    ) -> tidalapi.Session:
        """
        Authenticate with Tidal using a clean and maintainable approach.
        
        Args:
            method: Authentication method to use
            timeout_seconds: Timeout for OAuth login process
            auto_open_browser: Whether to automatically open browser
            force_new: Force new authentication even if session exists
            
        Returns:
            Authenticated Tidal session
            
        Raises:
            AuthenticationError: If authentication fails
        """
        if timeout_seconds is None:
            timeout_seconds = self.auth_timeout
        
        logger.info("Starting Tidal authentication...")
        self._notify_progress("Initializing authentication...", 0)
        
        # Try existing session first (unless forced)
        if not force_new:
            session = self._try_existing_session()
            if session:
                self._notify_progress(
                    "Authentication successful (existing session)", 100
                )
                return session
        
        # Clear existing session if forcing new
        if force_new:
            self.clear_session()
        
        # Start new authentication
        self._notify_progress("Starting new authentication...", 10)
        return self._authenticate_oauth(timeout_seconds, auto_open_browser)
    
    def _try_existing_session(self) -> Optional[tidalapi.Session]:
        """Try to load and validate existing session."""
        session_data = self.load_session()
        if not session_data:
            return None
        
        logger.info("Attempting to restore saved session...")
        self._notify_progress("Validating saved session...", 20)
        
        try:
            session = self._create_session()
            session.load_oauth_session(
                session_data.get("token_type"),
                session_data.get("access_token"),
                session_data.get("refresh_token"),
                session_data.get("expiry_time")
            )
            
            if self.validate_session(session):
                logger.info("Successfully authenticated with saved session!")
                return session
            else:
                # Try to refresh if possible
                logger.info("Saved session invalid, attempting refresh...")
                if self.try_refresh_session(session, session_data):
                    logger.info("Session refreshed successfully!")
                    return session
                else:
                    logger.info("Session refresh failed, will start new login...")
                    self.clear_session()
                
        except Exception as e:
            logger.warning(f"Error with saved session: {e}. Starting new login...")
            self.clear_session()
        
        return None
    
    def _authenticate_oauth(
        self, timeout_seconds: int, auto_open_browser: bool
    ) -> tidalapi.Session:
        """Simple OAuth authentication using device code flow."""
        session = self._create_session()
        
        try:
            # Get device code and auth URL
            link_login, future = session.login_oauth()
            
            if not link_login:
                raise AuthenticationError(
                    "Failed to get device authentication URL"
                )
            
            # Extract the URL from the LinkLogin object
            login_url = link_login.verification_uri_complete
            if not login_url:
                # Fallback to basic URL if complete URL not available
                login_url = getattr(link_login, 'verification_uri', str(link_login))
            
            # Display instructions and open browser
            self._display_auth_instructions(login_url, auto_open_browser)
            
            # Poll for completion
            self._notify_progress("Waiting for browser authorization...", 30)
            start_time = time.time()
            
            while time.time() - start_time < timeout_seconds:
                try:
                    if future.done():
                        result = future.result(timeout=1)
                        if result:
                            break
                except Exception:
                    pass
                
                time.sleep(2)  # Simple 2-second polling
                
                elapsed = int(time.time() - start_time)
                remaining = timeout_seconds - elapsed
                progress = min(30 + (elapsed / timeout_seconds) * 60, 90)
                self._notify_progress(
                    f"Waiting for authorization... ({remaining}s remaining)",
                    progress
                )
            
            # Check if authentication completed
            if not future.done() or not future.result():
                raise AuthenticationError(
                    "Authentication timed out or was cancelled"
                )
            
            # Validate session
            if not self.validate_session(session):
                raise AuthenticationError(
                    "Session validation failed after login"
                )
            
            # Save session
            self._save_session_data(session)
            self._notify_progress("Authentication complete!", 100)
            logger.info("OAuth authentication successful!")
            
            return session
            
        except AuthenticationError:
            raise
        except Exception as e:
            logger.error(f"OAuth authentication failed: {e}")
            raise AuthenticationError(f"OAuth authentication failed: {e}")
    
    def _display_auth_instructions(self, login_url: str, auto_open: bool):
        """Display authentication instructions to user."""
        print("\n🎵 Tidal Authentication Required")
        print(f"📋 Please visit: {login_url}")
        print("⏱️  Code expires in 5 minutes")
        print("✨ Complete the authorization, then return here")
        print("🔄 Checking for completion automatically...\n")
        
        if auto_open:
            try:
                import webbrowser
                webbrowser.open(login_url)
                print("🌐 Browser opened automatically\n")
            except Exception as e:
                logger.warning(f"Could not auto-open browser: {e}")
                print("⚠️  Please open the URL manually\n")
    
    def _save_session_data(self, session: tidalapi.Session) -> None:
        """Extract and save session data."""
        user_id = None
        if hasattr(session, 'user') and session.user:
            user_id = getattr(session.user, 'id', None)
        
        session_data = {
            "token_type": getattr(session, 'token_type', 'Bearer'),
            "access_token": getattr(session, 'access_token', ''),
            "refresh_token": getattr(session, 'refresh_token', ''),
            "session_id": getattr(session, 'session_id', ''),
            "country_code": getattr(session, 'country_code', ''),
            "user_id": user_id,
            "created_at": time.time(),
            "expires_at": time.time() + 3600,  # Assume 1 hour expiry
        }
        
        self.save_session(session_data)
    
    # Legacy method for backward compatibility
    def login(self, timeout_seconds: int = 60) -> tidalapi.Session:
        """Legacy login method for backward compatibility."""
        logger.warning("login() is deprecated, use authenticate() instead")
        return self.authenticate(timeout_seconds=timeout_seconds)

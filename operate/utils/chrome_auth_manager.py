#!/usr/bin/env python3
"""
Chrome Authentication Manager for Self-Operating Computer
Manages Google Chrome profile authentication for persistent browser sessions
"""

import os
import sys
import time
import tempfile
import subprocess
import logging
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
import json
from dataclasses import dataclass
from enum import Enum

# Self-operating computer style imports
try:
    from operate.utils.style import (
        ANSI_GREEN, ANSI_RESET, ANSI_YELLOW, ANSI_RED, 
        ANSI_BRIGHT_MAGENTA, ANSI_BLUE
    )
except ImportError:
    # Fallback if style module not available
    ANSI_GREEN = ANSI_RESET = ANSI_YELLOW = ANSI_RED = ANSI_BRIGHT_MAGENTA = ANSI_BLUE = ""

# Set up logging
logger = logging.getLogger(__name__)

class AuthStatus(Enum):
    """Authentication status enumeration"""
    AUTHENTICATED = "authenticated"
    FIRST_TIME = "first_time" 
    EXPIRED = "expired"
    ERROR = "error"

@dataclass
class AuthResult:
    """Result of authentication check or setup"""
    status: AuthStatus
    profile_path: str
    message: str
    success: bool = True
    error: Optional[str] = None

class ChromeAuthManager:
    """
    Chrome Authentication Manager
    
    Handles Google Chrome profile authentication for the self-operating computer.
    Provides persistent authentication across browser sessions.
    """
    
    def __init__(self, profile_name: str = "SelfOperatingComputer"):
        """
        Initialize Chrome Authentication Manager
        
        Args:
            profile_name: Name for the Chrome profile directory
        """
        self.profile_name = profile_name
        self.profile_path = self._get_profile_path()
        self.setup_timeout = 300  # 5 minutes for setup
        
        # Chrome arguments for Google compatibility
        self.chrome_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-extensions",
            "--no-first-run",
            "--no-service-autorun", 
            "--password-store=basic",
            "--disable-web-security",
            "--disable-features=VizDisplayCompositor"
        ]
        
        logger.info(f"ChromeAuthManager initialized with profile: {self.profile_path}")
    
    def _get_profile_path(self) -> str:
        """Get the Chrome profile directory path"""
        if sys.platform == "win32":
            base_path = os.path.join(os.environ.get('TEMP', tempfile.gettempdir()))
        else:
            base_path = tempfile.gettempdir()
        
        return os.path.join(base_path, f"{self.profile_name}_Profile")
    
    def check_authentication_status(self) -> AuthResult:
        """
        Check the current authentication status
        
        Returns:
            AuthResult with current authentication status
        """
        print(f"{ANSI_GREEN}[Chrome Auth]{ANSI_RESET} Checking authentication status...")
        
        # Check if profile directory exists
        if not os.path.exists(self.profile_path):
            return AuthResult(
                status=AuthStatus.FIRST_TIME,
                profile_path=self.profile_path,
                message="No profile found - first-time setup required",
                success=True
            )
        
        # Test authentication by checking Gmail access
        try:
            auth_test_result = self._test_gmail_authentication()
            
            if auth_test_result["authenticated"]:
                return AuthResult(
                    status=AuthStatus.AUTHENTICATED,
                    profile_path=self.profile_path,
                    message=f"Authentication verified: {auth_test_result['details']}",
                    success=True
                )
            elif auth_test_result["needs_signin"]:
                return AuthResult(
                    status=AuthStatus.EXPIRED,
                    profile_path=self.profile_path,
                    message="Authentication expired - re-authentication required",
                    success=True
                )
            else:
                return AuthResult(
                    status=AuthStatus.FIRST_TIME,
                    profile_path=self.profile_path,
                    message="No valid authentication found",
                    success=True
                )
                
        except Exception as e:
            logger.error(f"Authentication check failed: {e}")
            return AuthResult(
                status=AuthStatus.ERROR,
                profile_path=self.profile_path,
                message="Authentication check failed",
                success=False,
                error=str(e)
            )
    
    def _test_gmail_authentication(self) -> Dict[str, Any]:
        """
        Test Gmail authentication using Robot Framework
        
        Returns:
            Dictionary with authentication test results
        """
        try:
            # Use Robot Framework to test authentication
            robot_script = self._generate_auth_test_script()
            
            # Write temporary Robot Framework script
            temp_script_path = os.path.join(tempfile.gettempdir(), "auth_test.robot")
            with open(temp_script_path, 'w', encoding='utf-8') as f:
                f.write(robot_script)
            
            # Run Robot Framework test
            result = subprocess.run([
                sys.executable, "-m", "robot", 
                "--outputdir", tempfile.gettempdir(),
                "--output", "auth_test_output.xml",
                "--log", "NONE",
                "--report", "NONE",
                temp_script_path
            ], capture_output=True, text=True, timeout=30)
            
            # Parse results from Robot Framework output
            if result.returncode == 0:
                # Parse the output for authentication details
                output_lines = result.stdout.split('\n')
                for line in output_lines:
                    if "Gmail result:" in line:
                        gmail_title = line.split("Gmail result:")[-1].strip().strip('"')
                        
                        # Check authentication indicators
                        has_inbox = "inbox" in gmail_title.lower()
                        has_email = "@gmail.com" in gmail_title.lower() or "@googlemail.com" in gmail_title.lower()
                        needs_signin = "sign in" in gmail_title.lower()
                        
                        return {
                            "authenticated": has_inbox or has_email,
                            "needs_signin": needs_signin,
                            "details": gmail_title,
                            "success": True
                        }
            
            # Cleanup
            try:
                os.remove(temp_script_path)
                output_file = os.path.join(tempfile.gettempdir(), "auth_test_output.xml")
                if os.path.exists(output_file):
                    os.remove(output_file)
            except:
                pass
            
            return {
                "authenticated": False,
                "needs_signin": True,
                "details": "Authentication test failed",
                "success": False
            }
            
        except Exception as e:
            logger.error(f"Gmail authentication test failed: {e}")
            return {
                "authenticated": False,
                "needs_signin": True,
                "details": f"Test error: {str(e)}",
                "success": False
            }
    
    def _generate_auth_test_script(self) -> str:
        """Generate Robot Framework script for authentication testing"""
        chrome_args_str = str(self.chrome_args).replace("'", '"')
        return f'''*** Settings ***
Library    Browser

*** Test Cases ***
Test Authentication
    [Documentation]    Quick authentication test
    
    New Persistent Context    userDataDir={self.profile_path}    headless=True
    ...    args={chrome_args_str}
    
    New Page    https://gmail.com
    Sleep    5s
    
    ${{title}}=    Get Title
    Log    Gmail result: "${{title}}"    console=True
    
    Close Browser
'''
    
    def prompt_initial_setup(self) -> AuthResult:
        """
        Prompt user for initial Google authentication setup
        
        Returns:
            AuthResult indicating setup success/failure
        """
        print(f"\n{ANSI_BRIGHT_MAGENTA}╔═══════════════════════════════════════════════════════════════╗{ANSI_RESET}")
        print(f"{ANSI_BRIGHT_MAGENTA}║{ANSI_RESET}                 {ANSI_GREEN}GOOGLE AUTHENTICATION SETUP{ANSI_RESET}                 {ANSI_BRIGHT_MAGENTA}║{ANSI_RESET}")
        print(f"{ANSI_BRIGHT_MAGENTA}╚═══════════════════════════════════════════════════════════════╝{ANSI_RESET}")
        print(f"\n{ANSI_YELLOW}Welcome to Self-Operating Computer!{ANSI_RESET}")
        print(f"\n{ANSI_BLUE}Why do we need Google authentication?{ANSI_RESET}")
        print("• Access Gmail for email automation")
        print("• Use Google Drive for file operations")
        print("• Integrate with Google Calendar")
        print("• Enable Google Search automation")
        print("• Maintain persistent login across sessions")
        
        print(f"\n{ANSI_BLUE}Setup Process:{ANSI_RESET}")
        print("1. Chrome browser will open to Google sign-in")
        print("2. Sign in with your Google account")
        print("3. System will automatically detect completion")
        print("4. Your credentials will be securely saved")
        print(f"5. This is a {ANSI_GREEN}ONE-TIME{ANSI_RESET} setup process")
        
        print(f"\n{ANSI_YELLOW}Maximum setup time: 5 minutes{ANSI_RESET}")
        
        # Ask for user consent
        try:
            consent = input(f"\n{ANSI_GREEN}Proceed with Google authentication setup? (y/N): {ANSI_RESET}")
            if consent.lower() not in ['y', 'yes']:
                return AuthResult(
                    status=AuthStatus.ERROR,
                    profile_path=self.profile_path,
                    message="Setup cancelled by user",
                    success=False
                )
        except KeyboardInterrupt:
            print(f"\n{ANSI_RED}Setup cancelled{ANSI_RESET}")
            return AuthResult(
                status=AuthStatus.ERROR,
                profile_path=self.profile_path,
                message="Setup cancelled by user",
                success=False
            )
        
        # Create profile directory
        os.makedirs(self.profile_path, exist_ok=True)
        
        # Launch setup process
        print(f"\n{ANSI_GREEN}[Chrome Auth]{ANSI_RESET} Launching Google authentication setup...")
        
        try:
            setup_result = self._run_interactive_setup()
            
            if setup_result["success"]:
                # Verify setup worked
                print(f"{ANSI_GREEN}[Chrome Auth]{ANSI_RESET} Verifying authentication...")
                time.sleep(3)  # Allow time for profile to save
                
                auth_status = self.check_authentication_status()
                
                if auth_status.status == AuthStatus.AUTHENTICATED:
                    print(f"{ANSI_GREEN}✅ Setup completed successfully!{ANSI_RESET}")
                    print(f"{ANSI_GREEN}✅ Google authentication is now active{ANSI_RESET}")
                    return AuthResult(
                        status=AuthStatus.AUTHENTICATED,
                        profile_path=self.profile_path,
                        message="Initial setup completed successfully",
                        success=True
                    )
                else:
                    print(f"{ANSI_YELLOW}⚠️ Setup verification failed - please try again{ANSI_RESET}")
                    return AuthResult(
                        status=AuthStatus.ERROR,
                        profile_path=self.profile_path,
                        message="Setup verification failed",
                        success=False
                    )
            else:
                return AuthResult(
                    status=AuthStatus.ERROR,
                    profile_path=self.profile_path,
                    message=setup_result["message"],
                    success=False,
                    error=setup_result.get("error")
                )
                
        except Exception as e:
            logger.error(f"Setup process failed: {e}")
            return AuthResult(
                status=AuthStatus.ERROR,
                profile_path=self.profile_path,
                message="Setup process failed",
                success=False,
                error=str(e)
            )
    
    def _run_interactive_setup(self) -> Dict[str, Any]:
        """
        Run interactive setup using Robot Framework
        
        Returns:
            Dictionary with setup results
        """
        try:
            # Generate setup Robot Framework script
            setup_script = self._generate_setup_script()
            
            # Write temporary script
            temp_script_path = os.path.join(tempfile.gettempdir(), "chrome_setup.robot")
            with open(temp_script_path, 'w', encoding='utf-8') as f:
                f.write(setup_script)
            
            print(f"{ANSI_GREEN}[Chrome Auth]{ANSI_RESET} Opening Chrome for authentication...")
            
            # Run Robot Framework setup
            result = subprocess.run([
                sys.executable, "-m", "robot",
                "--outputdir", tempfile.gettempdir(),
                "--output", "setup_output.xml",
                "--log", "NONE",
                "--report", "NONE",
                temp_script_path
            ], capture_output=True, text=True, timeout=self.setup_timeout)
            
            # Parse results
            success = result.returncode == 0
            
            # Look for success indicators in output
            if success and "Authentication completed" in result.stdout:
                message = "Authentication setup completed"
            elif "timeout" in result.stdout.lower():
                message = "Setup timeout - please try again"
                success = False
            else:
                message = "Setup process completed"
            
            # Cleanup
            try:
                os.remove(temp_script_path)
                output_file = os.path.join(tempfile.gettempdir(), "setup_output.xml")
                if os.path.exists(output_file):
                    os.remove(output_file)
            except:
                pass
            
            return {
                "success": success,
                "message": message,
                "error": result.stderr if result.stderr else None
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "message": "Setup timeout exceeded",
                "error": "Process timed out after 5 minutes"
            }
        except Exception as e:
            return {
                "success": False,
                "message": "Setup process failed",
                "error": str(e)
            }
    
    def _generate_setup_script(self) -> str:
        """Generate Robot Framework script for interactive setup"""
        chrome_args_str = str(self.chrome_args).replace("'", '"')
        return f'''*** Settings ***
Library    Browser

*** Test Cases ***
Interactive Setup
    [Documentation]    Interactive Google authentication setup
    
    # Create profile directory
    Create Directory    {self.profile_path}
    
    # Launch Chrome with persistent profile
    New Persistent Context    userDataDir={self.profile_path}    headless=False
    ...    args={chrome_args_str}
    
    # Open Google sign-in
    New Page    https://accounts.google.com/signin
    Sleep    3s
    
    Log    Please complete Google sign-in in the browser window    console=True
    
    # Monitor for completion (5 minutes max)
    ${{completed}}=    Monitor Authentication    max_minutes=5
    
    Close Browser
    
    IF    ${{completed}}
        Log    Authentication completed successfully!    console=True
    ELSE
        Log    Authentication setup timeout    console=True
        Fail    Setup not completed within time limit
    END

*** Keywords ***
Monitor Authentication
    [Arguments]    ${{max_minutes}}=5
    
    ${{max_checks}}=    Evaluate    ${{max_minutes}} * 6
    
    FOR    ${{check}}    IN RANGE    ${{max_checks}}
        Sleep    10s
        
        TRY
            ${{title}}=    Get Title
            ${{url}}=    Get Url
            
            # Progress update every minute
            ${{minute_check}}=    Evaluate    ${{check}} % 6
            IF    ${{minute_check}} == 0 and ${{check}} > 0
                ${{elapsed}}=    Evaluate    round(${{check}} / 6, 1)
                Log    Still monitoring... ${{elapsed}} minutes elapsed    console=True
            END
            
            # Check for completion
            ${{completed}}=    Is Authentication Complete    ${{title}}    ${{url}}
            
            IF    ${{completed}}
                ${{elapsed}}=    Evaluate    round(${{check}} / 6, 1)
                Log    Authentication detected after ${{elapsed}} minutes!    console=True
                RETURN    True
            END
            
        EXCEPT
            Log    Continuing to monitor...    console=True
        END
    END
    
    RETURN    False

Is Authentication Complete
    [Arguments]    ${{title}}    ${{url}}
    
    # Skip sign-in pages
    ${{signin_keywords}}=    Create List    sign in    signin    choose an account
    FOR    ${{keyword}}    IN    @{{signin_keywords}}
        ${{is_signin}}=    Evaluate    "${{keyword}}" in "${{title}}".lower()
        IF    ${{is_signin}}
            RETURN    False
        END
    END
    
    # Check for success indicators
    ${{success_keywords}}=    Create List    google account    my account    inbox    gmail    @gmail.com    myaccount.google.com    mail.google.com
    FOR    ${{keyword}}    IN    @{{success_keywords}}
        ${{has_success}}=    Evaluate    "${{keyword}}" in "${{title}}".lower() or "${{keyword}}" in "${{url}}".lower()
        IF    ${{has_success}}
            RETURN    True
        END
    END
    
    RETURN    False
'''
    
    def get_profile_path(self) -> str:
        """Get the Chrome profile directory path"""
        return self.profile_path

# Convenience functions for integration
def ensure_chrome_authentication(profile_name: str = "SelfOperatingComputer") -> Tuple[bool, str, str]:
    """
    Ensure Chrome authentication is set up and working
    
    Args:
        profile_name: Name for the Chrome profile
        
    Returns:
        Tuple of (success, profile_path, message)
    """
    auth_manager = ChromeAuthManager(profile_name)
    
    # Check current status
    auth_result = auth_manager.check_authentication_status()
    
    if auth_result.status == AuthStatus.AUTHENTICATED:
        print(f"{ANSI_GREEN}✅ Google authentication is active{ANSI_RESET}")
        return True, auth_result.profile_path, auth_result.message
    
    elif auth_result.status == AuthStatus.FIRST_TIME:
        print(f"{ANSI_YELLOW}🔑 First-time setup required{ANSI_RESET}")
        setup_result = auth_manager.prompt_initial_setup()
        
        if setup_result.success:
            return True, setup_result.profile_path, setup_result.message
        else:
            print(f"{ANSI_RED}❌ Authentication setup failed: {setup_result.message}{ANSI_RESET}")
            return False, setup_result.profile_path, setup_result.message
    
    elif auth_result.status == AuthStatus.EXPIRED:
        print(f"{ANSI_YELLOW}⚠️ Authentication expired{ANSI_RESET}")
        # For expired auth, we can try to re-authenticate
        setup_result = auth_manager.prompt_initial_setup()
        
        if setup_result.success:
            return True, setup_result.profile_path, setup_result.message
        else:
            print(f"{ANSI_RED}❌ Re-authentication failed: {setup_result.message}{ANSI_RESET}")
            return False, setup_result.profile_path, setup_result.message
    
    else:
        print(f"{ANSI_RED}❌ Authentication error: {auth_result.message}{ANSI_RESET}")
        return False, auth_result.profile_path, auth_result.message

def get_chrome_profile_path(profile_name: str = "SelfOperatingComputer") -> Optional[str]:
    """
    Get Chrome profile path if authentication is active
    
    Args:
        profile_name: Name for the Chrome profile
        
    Returns:
        Profile path if authenticated, None otherwise
    """
    auth_manager = ChromeAuthManager(profile_name)
    auth_result = auth_manager.check_authentication_status()
    
    if auth_result.status == AuthStatus.AUTHENTICATED:
        return auth_result.profile_path
    
    return None 
#!/usr/bin/env python3
"""
Intelligent File Upload Actions for Browser Use
Provides secure file selection and upload capabilities with full system search
"""

import os
import pathlib
import glob
import string
import asyncio
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pydantic import BaseModel, Field

try:
    from browser_use import Controller, ActionResult
    from playwright.async_api import Page
    BROWSER_USE_AVAILABLE = True
except ImportError:
    # Fallback for development/testing
    BROWSER_USE_AVAILABLE = False
    class ActionResult:
        def __init__(self, extracted_content=None, error=None, include_in_memory=False):
            self.extracted_content = extracted_content
            self.error = error
            self.include_in_memory = include_in_memory

# Set up logging
logger = logging.getLogger(__name__)

@dataclass
class FileCandidate:
    """Represents a file candidate for upload"""
    path: str
    filename: str
    modified: float
    size: int
    score: float = 0.0  # Relevance score for ranking

class IntelligentFileUploader:
    """
    Intelligent file selection and upload system with full system search capability
    """
    
    def __init__(self):
        self.controller = Controller() if BROWSER_USE_AVAILABLE else None
        
        # Default search directories (full system search by default)
        self.default_search_directories = self._get_default_search_directories()
        
        # Directories to exclude for performance and relevance
        self.excluded_directories = [
            "Windows", "Program Files", "Program Files (x86)", "System32",
            "node_modules", ".git", "__pycache__", ".npm", ".cache",
            "AppData/Local/Temp", "Library/Caches", "/usr", "/var",
            "/proc", "/sys", "/dev", ".vscode", ".idea", ".svn",
            "Temporary Internet Files", "Local Settings", "Application Data"
        ]
        
        # Safe mode directories (privacy-conscious option)
        self.safe_mode_directories = [
            os.path.join(os.path.expanduser("~"), "Downloads"),
            os.path.join(os.path.expanduser("~"), "Documents"),
            os.path.join(os.path.expanduser("~"), "Desktop")
        ]
        
        logger.info("IntelligentFileUploader initialized with full system search")
    
    def _get_default_search_directories(self) -> List[str]:
        """Get default search directories based on operating system"""
        directories = [os.path.expanduser("~")]  # Start with user home
        
        if os.name == 'nt':  # Windows
            # Add all available drives
            for drive in string.ascii_uppercase:
                drive_path = f"{drive}:\\"
                if os.path.exists(drive_path):
                    directories.append(drive_path)
        else:  # Mac/Linux
            directories.append("/")  # Root directory
        
        return directories
    
    def _should_skip_directory(self, dir_path: str) -> bool:
        """Check if directory should be skipped for performance/relevance"""
        dir_name = os.path.basename(dir_path).lower()
        return any(excluded.lower() in dir_name for excluded in self.excluded_directories)
    
    def _extract_keywords(self, file_description: str) -> List[str]:
        """Extract search keywords from file description"""
        # Remove common stop words and extract meaningful terms
        stop_words = {'file', 'the', 'a', 'an', 'and', 'or', 'but', 'from', 'with'}
        keywords = [word.lower() for word in file_description.split() 
                   if word.lower() not in stop_words and len(word) > 1]
        return keywords
    
    def _calculate_relevance_score(self, candidate: FileCandidate, keywords: List[str]) -> float:
        """Calculate relevance score for file candidate"""
        filename_lower = candidate.filename.lower()
        score = 0.0
        
        # Exact keyword matches get highest score
        for keyword in keywords:
            if keyword in filename_lower:
                # Boost score based on how much of the filename the keyword represents
                keyword_ratio = len(keyword) / len(filename_lower)
                score += 10.0 * keyword_ratio
        
        # Partial matches get lower scores
        for keyword in keywords:
            for part in filename_lower.split('.')[:-1]:  # Exclude extension
                if keyword in part:
                    score += 3.0
        
        # Recency bonus (files modified in last 30 days get bonus)
        import time
        days_old = (time.time() - candidate.modified) / (24 * 3600)
        if days_old < 30:
            score += max(0, 2.0 - (days_old / 15))  # Up to 2 points for recent files
        
        # File size considerations (neither too small nor too large is preferred)
        if 1024 < candidate.size < 100 * 1024 * 1024:  # 1KB to 100MB
            score += 1.0
        
        return score
    
    def find_matching_files(self, file_description: str, 
                          search_directories: Optional[List[str]] = None,
                          safe_mode: bool = False,
                          max_results: int = 20) -> List[FileCandidate]:
        """
        Find files matching the description across the system
        
        Args:
            file_description: Description of the file to find (e.g., "n8n file")
            search_directories: Custom directories to search (None = use defaults)
            safe_mode: If True, only search Downloads/Documents/Desktop
            max_results: Maximum number of candidates to return
            
        Returns:
            List of FileCandidate objects sorted by relevance
        """
        logger.info(f"Searching for files matching: '{file_description}'")
        
        # Determine search scope
        if safe_mode:
            directories = self.safe_mode_directories
            logger.info("Using safe mode - searching Downloads/Documents/Desktop only")
        elif search_directories:
            directories = search_directories
            logger.info(f"Using custom search directories: {directories}")
        else:
            directories = self.default_search_directories
            logger.info("Using full system search mode")
        
        keywords = self._extract_keywords(file_description)
        logger.info(f"Search keywords: {keywords}")
        
        candidates = []
        
        # Search through all directories
        for search_dir in directories:
            if not os.path.exists(search_dir):
                continue
            
            logger.info(f"Searching directory: {search_dir}")
            
            try:
                # Recursive search through directory tree
                for root, dirs, files in os.walk(search_dir):
                    # Skip excluded directories
                    if self._should_skip_directory(root):
                        dirs[:] = []  # Don't recurse into subdirectories
                        continue
                    
                    # Limit recursion depth for performance
                    current_depth = root.replace(search_dir, '').count(os.sep)
                    if current_depth > 10:  # Max 10 levels deep
                        continue
                    
                    for file in files:
                        file_path = os.path.join(root, file)
                        filename_lower = file.lower()
                        
                        # Check if any keyword matches filename
                        if any(keyword in filename_lower for keyword in keywords):
                            try:
                                candidate = FileCandidate(
                                    path=file_path,
                                    filename=file,
                                    modified=os.path.getmtime(file_path),
                                    size=os.path.getsize(file_path)
                                )
                                candidate.score = self._calculate_relevance_score(candidate, keywords)
                                candidates.append(candidate)
                                
                                # Stop if we have enough candidates for performance
                                if len(candidates) >= max_results * 3:
                                    break
                                    
                            except (OSError, PermissionError):
                                # Skip files we can't access
                                continue
                    
                    if len(candidates) >= max_results * 3:
                        break
                        
            except (OSError, PermissionError) as e:
                logger.warning(f"Cannot access directory {search_dir}: {e}")
                continue
        
        # Fallback: Look for common file extensions if no keyword matches
        if not candidates and keywords:
            logger.info("No keyword matches found, trying extension-based search")
            common_extensions = ['.pdf', '.doc', '.docx', '.txt', '.csv', 
                               '.xlsx', '.json', '.xml', '.zip', '.exe']
            
            for search_dir in directories[:1]:  # Just search user home for extensions
                if not os.path.exists(search_dir):
                    continue
                    
                for ext in common_extensions:
                    try:
                        pattern = os.path.join(search_dir, f"**/*{ext}")
                        for file_path in glob.glob(pattern, recursive=True)[:50]:  # Limit results
                            if os.path.isfile(file_path):
                                candidate = FileCandidate(
                                    path=file_path,
                                    filename=os.path.basename(file_path),
                                    modified=os.path.getmtime(file_path),
                                    size=os.path.getsize(file_path),
                                    score=1.0  # Lower score for extension matches
                                )
                                candidates.append(candidate)
                    except Exception:
                        continue
        
        # Sort by relevance score (highest first)
        candidates.sort(key=lambda x: x.score, reverse=True)
        
        # Return top candidates
        result = candidates[:max_results]
        logger.info(f"Found {len(result)} file candidates")
        
        return result
    
    def select_best_file(self, candidates: List[FileCandidate], 
                        file_description: str) -> Optional[FileCandidate]:
        """Select the best file from candidates"""
        if not candidates:
            return None
        
        # Return highest scoring candidate
        best = candidates[0]
        logger.info(f"Selected file: {best.filename} (score: {best.score:.2f})")
        
        # Log alternatives for debugging
        if len(candidates) > 1:
            alternatives = [f"{c.filename} ({c.score:.1f})" for c in candidates[1:6]]
            logger.info(f"Alternatives found: {alternatives}")
        
        return best

# Initialize the controller and register actions
file_uploader = IntelligentFileUploader()

# Pydantic models for action parameters
class FindUploadParams(BaseModel):
    file_description: str = Field(description="Description of file to find (e.g., 'n8n file', 'invoice PDF')")
    selector: str = Field(description="CSS selector for the file input element")
    safe_mode: bool = Field(default=False, description="If True, only search Downloads/Documents/Desktop")

class UploadParams(BaseModel):
    file_path: str = Field(description="Exact path to the file")
    selector: str = Field(description="CSS selector for the file input element")

if BROWSER_USE_AVAILABLE and file_uploader.controller:
    
    @file_uploader.controller.action('Find and upload file', param_model=FindUploadParams)
    async def find_and_upload_file(params: FindUploadParams, page) -> ActionResult:
        """
        Intelligent file selection and upload with full system search
        Uses Playwright's file chooser pattern to handle attachment buttons properly
        """
        try:
            logger.info(f"Finding and uploading file: '{params.file_description}' to selector: {params.selector}")
            
            # Find matching files
            candidates = file_uploader.find_matching_files(
                file_description=params.file_description,
                safe_mode=params.safe_mode
            )
            
            if not candidates:
                return ActionResult(
                    error=f"No files found matching '{params.file_description}'. "
                          f"Try being more specific or check if the file exists."
                )
            
            # Select best candidate
            selected_file = file_uploader.select_best_file(candidates, params.file_description)
            if not selected_file:
                return ActionResult(error="Could not select appropriate file from candidates")
            
            logger.info(f"Selected file for upload: {selected_file.path}")
            
            # Try two approaches for file upload
            
            # Approach 1: Direct set_input_files (for hidden file inputs)
            try:
                # First try to find a file input directly
                file_input = page.locator('input[type="file"]')
                if await file_input.count() > 0:
                    await file_input.set_input_files(selected_file.path)
                    logger.info("Successfully uploaded using direct file input")
                else:
                    raise Exception("No file input found, trying file chooser pattern")
                    
            except Exception as e:
                logger.info(f"Direct file input failed: {e}, trying file chooser pattern")
                
                # Approach 2: File chooser pattern (for buttons that open file dialogs)
                try:
                    # Set up file chooser listener before clicking
                    file_chooser_promise = page.wait_for_event('filechooser')
                    
                    # Click the element that opens the file dialog
                    await page.locator(params.selector).click()
                    
                    # Wait for and handle the file chooser
                    file_chooser = await file_chooser_promise
                    await file_chooser.set_files(selected_file.path)
                    
                    logger.info("Successfully uploaded using file chooser pattern")
                    
                except Exception as chooser_error:
                    logger.error(f"File chooser pattern also failed: {chooser_error}")
                    raise Exception(f"Both upload methods failed. Direct input: {e}, File chooser: {chooser_error}")
            
            # Success message with details
            success_msg = f"✓ uploaded {selected_file.filename}"
            if len(candidates) > 1:
                success_msg += f" (found {len(candidates)} candidates, selected best match)"
            
            logger.info(f"Successfully uploaded: {selected_file.path}")
            return ActionResult(extracted_content=success_msg, include_in_memory=True)
            
        except Exception as e:
            error_msg = f"File upload failed: {str(e)}"
            logger.error(error_msg)
            return ActionResult(error=error_msg)
    
    @file_uploader.controller.action('Upload specific file', param_model=UploadParams)
    async def upload_specific_file(params: UploadParams, page, available_file_paths: List[str] = None) -> ActionResult:
        """
        Direct file upload when exact path is known
        Uses Playwright's file chooser pattern to handle attachment buttons properly
        """
        try:
            # Validate file path if whitelist provided
            if available_file_paths and params.file_path not in available_file_paths:
                return ActionResult(error=f"File path not whitelisted: {params.file_path}")
            
            # Check file existence
            if not os.path.exists(params.file_path):
                return ActionResult(error=f"File not found: {params.file_path}")
            
            logger.info(f"Uploading specific file: {params.file_path} to selector: {params.selector}")
            
            # Try two approaches for file upload
            
            # Approach 1: Direct set_input_files (for hidden file inputs)
            try:
                # First try to find a file input directly
                file_input = page.locator('input[type="file"]')
                if await file_input.count() > 0:
                    await file_input.set_input_files(params.file_path)
                    logger.info("Successfully uploaded using direct file input")
                else:
                    raise Exception("No file input found, trying file chooser pattern")
                    
            except Exception as e:
                logger.info(f"Direct file input failed: {e}, trying file chooser pattern")
                
                # Approach 2: File chooser pattern (for buttons that open file dialogs)
                try:
                    # Set up file chooser listener before clicking
                    file_chooser_promise = page.wait_for_event('filechooser')
                    
                    # Click the element that opens the file dialog
                    await page.locator(params.selector).click()
                    
                    # Wait for and handle the file chooser
                    file_chooser = await file_chooser_promise
                    await file_chooser.set_files(params.file_path)
                    
                    logger.info("Successfully uploaded using file chooser pattern")
                    
                except Exception as chooser_error:
                    logger.error(f"File chooser pattern also failed: {chooser_error}")
                    raise Exception(f"Both upload methods failed. Direct input: {e}, File chooser: {chooser_error}")
            
            filename = os.path.basename(params.file_path)
            logger.info(f"Successfully uploaded specific file: {params.file_path}")
            return ActionResult(extracted_content=f"✓ uploaded {filename}")
            
        except Exception as e:
            error_msg = f"Specific file upload failed: {str(e)}"
            logger.error(error_msg)
            return ActionResult(error=error_msg)

    # Export the controller for integration
    controller = file_uploader.controller
    
else:
    logger.warning("Browser Use not available - file upload actions not registered")
    controller = None

# Export for integration with BrowserAgent  
__all__ = ['IntelligentFileUploader', 'find_and_upload_file', 'upload_specific_file', 'controller', 'BROWSER_USE_AVAILABLE', 'FILE_UPLOAD_AVAILABLE']

# Export availability flags
FILE_UPLOAD_AVAILABLE = BROWSER_USE_AVAILABLE and (controller is not None) 
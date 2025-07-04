"""
OCR Manager with optimized EasyOCR initialization

This module provides a singleton pattern for EasyOCR instances while maintaining
flexibility for different models and languages.
"""

import threading
import time
from typing import Dict, Any, Optional, List
from operate.config import Config

# Global imports (will be imported only when needed)
_easyocr = None
_ocr_instances = {}
_lock = threading.Lock()

# Load configuration
config = Config()

class OCRManager:
    """
    Singleton manager for EasyOCR instances
    
    Features:
    - Maintains separate instances for different language combinations
    - Thread-safe initialization
    - Automatic cleanup and memory management
    - Performance tracking
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            with _lock:
                if cls._instance is None:
                    cls._instance = super(OCRManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            with _lock:
                if not self._initialized:
                    self.readers: Dict[str, Any] = {}
                    self.initialization_times: Dict[str, float] = {}
                    self.usage_counts: Dict[str, int] = {}
                    self.last_used: Dict[str, float] = {}
                    OCRManager._initialized = True
    
    def get_reader(self, languages: List[str] = None, model_name: str = None) -> Any:
        """
        Get or create an EasyOCR reader instance
        
        Args:
            languages: List of language codes (default: ["en"])
            model_name: Optional model name for tracking (for future use)
            
        Returns:
            EasyOCR Reader instance
        """
        if languages is None:
            languages = ["en"]
        
        # Create a unique key for this language combination
        lang_key = "_".join(sorted(languages))
        
        with _lock:
            # Check if we already have a reader for this language combination
            if lang_key in self.readers:
                # Update usage tracking
                self.usage_counts[lang_key] = self.usage_counts.get(lang_key, 0) + 1
                self.last_used[lang_key] = time.time()
                
                if config.verbose:
                    print(f"[OCRManager] Reusing existing EasyOCR reader for {lang_key} (used {self.usage_counts[lang_key]} times)")
                
                return self.readers[lang_key]
            
            # Initialize EasyOCR for the first time
            if config.verbose:
                print(f"[OCRManager] Initializing new EasyOCR reader for languages: {languages}")
            
            start_time = time.time()
            
            # Import EasyOCR only when needed
            global _easyocr
            if _easyocr is None:
                import easyocr
                _easyocr = easyocr
            
            # Create new reader instance
            reader = _easyocr.Reader(languages)
            
            # Track initialization time
            init_time = time.time() - start_time
            self.initialization_times[lang_key] = init_time
            self.usage_counts[lang_key] = 1
            self.last_used[lang_key] = time.time()
            
            # Store the reader
            self.readers[lang_key] = reader
            
            if config.verbose:
                print(f"[OCRManager] EasyOCR reader initialized in {init_time:.2f}s for {lang_key}")
            
            return reader
    
    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        with _lock:
            total_readers = len(self.readers)
            total_init_time = sum(self.initialization_times.values())
            total_usage = sum(self.usage_counts.values())
            
            return {
                'total_readers': total_readers,
                'total_init_time': total_init_time,
                'total_usage': total_usage,
                'average_init_time': total_init_time / max(1, total_readers),
                'readers_by_language': list(self.readers.keys()),
                'usage_counts': self.usage_counts.copy(),
                'initialization_times': self.initialization_times.copy()
            }
    
    def cleanup_unused_readers(self, max_age_seconds: int = 300):
        """
        Clean up readers that haven't been used recently
        
        Args:
            max_age_seconds: Maximum age in seconds before cleanup
        """
        current_time = time.time()
        with _lock:
            to_remove = []
            for lang_key, last_use_time in self.last_used.items():
                if current_time - last_use_time > max_age_seconds:
                    to_remove.append(lang_key)
            
            for lang_key in to_remove:
                if config.verbose:
                    print(f"[OCRManager] Cleaning up unused reader: {lang_key}")
                
                del self.readers[lang_key]
                del self.initialization_times[lang_key]
                del self.usage_counts[lang_key]
                del self.last_used[lang_key]
    
    def reset(self):
        """Reset all readers (useful for testing)"""
        with _lock:
            self.readers.clear()
            self.initialization_times.clear()
            self.usage_counts.clear()
            self.last_used.clear()
            
            if config.verbose:
                print("[OCRManager] All readers reset")

# Global instance
ocr_manager = OCRManager()

def get_ocr_reader(languages: List[str] = None, model_name: str = None) -> Any:
    """
    Convenience function to get an OCR reader
    
    Args:
        languages: List of language codes (default: ["en"])
        model_name: Optional model name for tracking
        
    Returns:
        EasyOCR Reader instance
    """
    return ocr_manager.get_reader(languages, model_name)

def get_ocr_stats() -> Dict[str, Any]:
    """Get OCR performance statistics"""
    return ocr_manager.get_stats()

def cleanup_ocr_readers(max_age_seconds: int = 300):
    """Clean up unused OCR readers"""
    ocr_manager.cleanup_unused_readers(max_age_seconds)

def reset_ocr_manager():
    """Reset OCR manager (useful for testing)"""
    ocr_manager.reset() 
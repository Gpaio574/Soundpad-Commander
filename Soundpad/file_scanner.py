"""
File Scanner for Soundpad Commander.

Scans directories for audio files and organizes them into categories
based on folder structure for import into Soundpad.
"""

import os
import mimetypes
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple, NamedTuple, Any
from dataclasses import dataclass
from collections import defaultdict


class AudioFileInfo(NamedTuple):
    """Information about an audio file."""
    path: str
    name: str
    size: int
    extension: str
    mime_type: Optional[str]


@dataclass 
class CategoryInfo:
    """Information about a scanned category (folder)."""
    name: str
    path: str
    audio_files: List[AudioFileInfo]
    total_files: int
    total_size: int
    
    @property
    def size_mb(self) -> float:
        """Get total size in MB."""
        return self.total_size / (1024 * 1024)


class FileScanner:
    """
    Scans directories for audio files and organizes them by category.
    
    Supports common audio formats and provides detailed information
    about discovered files and categories for Soundpad import.
    """
    
    # Supported audio file extensions
    SUPPORTED_AUDIO_EXTENSIONS = {
        '.mp3', '.wav', '.ogg', '.m4a', '.aac', '.flac', '.wma',
        '.mp4', '.avi', '.mov', '.mkv', '.webm'  # Video files with audio
    }
    
    # Minimum file size to consider (in bytes) - filters out very small files
    MIN_FILE_SIZE = 1024  # 1KB
    
    def __init__(self, ignore_hidden: bool = True, follow_symlinks: bool = False):
        """
        Initialize file scanner.
        
        Args:
            ignore_hidden: Skip hidden files and directories
            follow_symlinks: Follow symbolic links during scanning
        """
        self.ignore_hidden = ignore_hidden
        self.follow_symlinks = follow_symlinks
        self._initialize_mime_types()
    
    def _initialize_mime_types(self) -> None:
        """Initialize MIME type detection."""
        # Add common audio MIME types
        mimetypes.init()
        audio_types = {
            '.mp3': 'audio/mpeg',
            '.wav': 'audio/wav', 
            '.ogg': 'audio/ogg',
            '.m4a': 'audio/mp4',
            '.aac': 'audio/aac',
            '.flac': 'audio/flac',
            '.wma': 'audio/x-ms-wma'
        }
        
        for ext, mime_type in audio_types.items():
            mimetypes.add_type(mime_type, ext)
    
    def is_audio_file(self, file_path: str) -> bool:
        """
        Check if a file is a supported audio file.
        
        Args:
            file_path: Path to file to check
            
        Returns:
            True if file is a supported audio format
        """
        if not os.path.isfile(file_path):
            return False
        
        # Check file size
        try:
            if os.path.getsize(file_path) < self.MIN_FILE_SIZE:
                return False
        except OSError:
            return False
        
        # Check extension
        extension = Path(file_path).suffix.lower()
        if extension not in self.SUPPORTED_AUDIO_EXTENSIONS:
            return False
        
        return True
    
    def _should_skip_directory(self, dir_path: str) -> bool:
        """
        Check if directory should be skipped.
        
        Args:
            dir_path: Directory path to check
            
        Returns:
            True if directory should be skipped
        """
        if self.ignore_hidden:
            dir_name = os.path.basename(dir_path)
            if dir_name.startswith('.'):
                return True
        
        # Skip common system/temp directories
        skip_dirs = {
            '__pycache__', '.git', '.svn', '.hg', 
            'Thumbs.db', 'Desktop.ini', '.DS_Store'
        }
        
        dir_name = os.path.basename(dir_path)
        return dir_name in skip_dirs
    
    def _should_skip_file(self, file_path: str) -> bool:
        """
        Check if file should be skipped.
        
        Args:
            file_path: File path to check
            
        Returns:
            True if file should be skipped
        """
        if self.ignore_hidden:
            file_name = os.path.basename(file_path)
            if file_name.startswith('.'):
                return True
        
        return False
    
    def scan_directory(self, root_path: str, max_depth: Optional[int] = None) -> Dict[str, CategoryInfo]:
        """
        Scan a directory tree for audio files organized by subdirectories.
        
        Args:
            root_path: Root directory to scan
            max_depth: Maximum depth to scan (None for unlimited)
            
        Returns:
            Dictionary mapping category names to CategoryInfo objects
            
        Raises:
            FileNotFoundError: If root_path doesn't exist
            PermissionError: If access is denied to root_path
        """
        root_path = os.path.abspath(root_path)
        
        if not os.path.exists(root_path):
            raise FileNotFoundError(f"Directory not found: {root_path}")
        
        if not os.path.isdir(root_path):
            raise NotADirectoryError(f"Path is not a directory: {root_path}")
        
        categories = {}
        
        try:
            for item in os.listdir(root_path):
                item_path = os.path.join(root_path, item)
                
                if not os.path.isdir(item_path):
                    continue
                
                if self._should_skip_directory(item_path):
                    continue
                
                # Scan this subdirectory as a category
                category_info = self._scan_category_directory(item_path, max_depth)
                if category_info and category_info.audio_files:
                    categories[item] = category_info
        
        except PermissionError as e:
            raise PermissionError(f"Permission denied accessing directory: {root_path}") from e
        
        return categories
    
    def _scan_category_directory(self, category_path: str, max_depth: Optional[int] = None) -> Optional[CategoryInfo]:
        """
        Scan a single category directory for audio files.
        
        Args:
            category_path: Path to category directory
            max_depth: Maximum depth to scan within category
            
        Returns:
            CategoryInfo object or None if no audio files found
        """
        audio_files = []
        total_size = 0
        
        try:
            for root, dirs, files in os.walk(category_path, followlinks=self.follow_symlinks):
                # Check depth limit
                if max_depth is not None:
                    depth = root[len(category_path):].count(os.sep)
                    if depth >= max_depth:
                        dirs.clear()  # Don't go deeper
                        continue
                
                # Filter out directories to skip
                dirs[:] = [d for d in dirs if not self._should_skip_directory(os.path.join(root, d))]
                
                # Process audio files in this directory
                for file_name in files:
                    file_path = os.path.join(root, file_name)
                    
                    if self._should_skip_file(file_path):
                        continue
                    
                    if self.is_audio_file(file_path):
                        try:
                            file_size = os.path.getsize(file_path)
                            file_ext = Path(file_path).suffix.lower()
                            mime_type, _ = mimetypes.guess_type(file_path)
                            
                            audio_file_info = AudioFileInfo(
                                path=file_path,
                                name=file_name,
                                size=file_size,
                                extension=file_ext,
                                mime_type=mime_type
                            )
                            
                            audio_files.append(audio_file_info)
                            total_size += file_size
                            
                        except OSError:
                            # Skip files we can't access
                            continue
        
        except PermissionError:
            # Return partial results if we can't access some subdirectories
            pass
        
        if not audio_files:
            return None
        
        category_name = os.path.basename(category_path)
        return CategoryInfo(
            name=category_name,
            path=category_path,
            audio_files=audio_files,
            total_files=len(audio_files),
            total_size=total_size
        )
    
    def scan_single_directory(self, directory_path: str, category_name: Optional[str] = None) -> Optional[CategoryInfo]:
        """
        Scan a single directory (non-recursive) for audio files.
        
        Args:
            directory_path: Directory to scan
            category_name: Custom category name (defaults to directory name)
            
        Returns:
            CategoryInfo object or None if no audio files found
        """
        if not os.path.exists(directory_path) or not os.path.isdir(directory_path):
            return None
        
        if category_name is None:
            category_name = os.path.basename(directory_path)
        
        audio_files = []
        total_size = 0
        
        try:
            for item in os.listdir(directory_path):
                item_path = os.path.join(directory_path, item)
                
                if not os.path.isfile(item_path):
                    continue
                
                if self._should_skip_file(item_path):
                    continue
                
                if self.is_audio_file(item_path):
                    try:
                        file_size = os.path.getsize(item_path)
                        file_ext = Path(item_path).suffix.lower()
                        mime_type, _ = mimetypes.guess_type(item_path)
                        
                        audio_file_info = AudioFileInfo(
                            path=item_path,
                            name=item,
                            size=file_size,
                            extension=file_ext,
                            mime_type=mime_type
                        )
                        
                        audio_files.append(audio_file_info)
                        total_size += file_size
                        
                    except OSError:
                        continue
        
        except PermissionError:
            return None
        
        if not audio_files:
            return None
        
        return CategoryInfo(
            name=category_name,
            path=directory_path,
            audio_files=audio_files,
            total_files=len(audio_files),
            total_size=total_size
        )
    
    def get_scan_statistics(self, categories: Dict[str, CategoryInfo]) -> Dict[str, Any]:
        """
        Get statistics about scanned categories.
        
        Args:
            categories: Categories returned by scan_directory()
            
        Returns:
            Dictionary containing scan statistics
        """
        if not categories:
            return {
                'total_categories': 0,
                'total_files': 0,
                'total_size': 0,
                'total_size_mb': 0.0,
                'file_types': {},
                'largest_category': None,
                'average_files_per_category': 0.0
            }
        
        total_files = sum(cat.total_files for cat in categories.values())
        total_size = sum(cat.total_size for cat in categories.values())
        
        # Count file types
        file_types = defaultdict(int)
        for category in categories.values():
            for audio_file in category.audio_files:
                file_types[audio_file.extension] += 1
        
        # Find largest category
        largest_category = max(categories.values(), key=lambda c: c.total_files)
        
        return {
            'total_categories': len(categories),
            'total_files': total_files,
            'total_size': total_size,
            'total_size_mb': total_size / (1024 * 1024),
            'file_types': dict(file_types),
            'largest_category': {
                'name': largest_category.name,
                'files': largest_category.total_files,
                'size_mb': largest_category.size_mb
            },
            'average_files_per_category': total_files / len(categories)
        }
    
    def validate_category_for_soundpad(self, category: CategoryInfo) -> List[str]:
        """
        Validate a category for Soundpad compatibility.
        
        Args:
            category: Category to validate
            
        Returns:
            List of validation warnings/issues
        """
        issues = []
        
        # Check for very large categories (Soundpad performance)
        if category.total_files > 1000:
            issues.append(f"Large category ({category.total_files} files) may impact Soundpad performance")
        
        # Check for very large files
        large_files = [f for f in category.audio_files if f.size > 50 * 1024 * 1024]  # 50MB
        if large_files:
            issues.append(f"{len(large_files)} files are very large (>50MB) and may cause playback issues")
        
        # Check for unusual file types
        video_files = [f for f in category.audio_files if f.extension in {'.mp4', '.avi', '.mov', '.mkv', '.webm'}]
        if video_files:
            issues.append(f"{len(video_files)} video files found - only audio will be used in Soundpad")
        
        # Check file path lengths (Windows limitation)
        long_paths = [f for f in category.audio_files if len(f.path) > 260]
        if long_paths:
            issues.append(f"{len(long_paths)} files have very long paths that may cause issues on Windows")
        
        return issues
    
    def filter_categories_by_size(self, categories: Dict[str, CategoryInfo], 
                                 min_files: int = 1, max_files: Optional[int] = None) -> Dict[str, CategoryInfo]:
        """
        Filter categories by number of files.
        
        Args:
            categories: Categories to filter
            min_files: Minimum number of files required
            max_files: Maximum number of files allowed (None for no limit)
            
        Returns:
            Filtered categories dictionary
        """
        filtered = {}
        
        for name, category in categories.items():
            if category.total_files < min_files:
                continue
            
            if max_files is not None and category.total_files > max_files:
                continue
            
            filtered[name] = category
        
        return filtered
    
    def get_supported_extensions(self) -> Set[str]:
        """Get set of supported audio file extensions."""
        return self.SUPPORTED_AUDIO_EXTENSIONS.copy()


def scan_for_soundpad_categories(root_directory: str, 
                               min_files_per_category: int = 1,
                               max_depth: Optional[int] = None) -> Dict[str, CategoryInfo]:
    """
    Convenience function to scan for Soundpad categories.
    
    Args:
        root_directory: Directory to scan for sound folders
        min_files_per_category: Minimum files required per category
        max_depth: Maximum depth to scan
        
    Returns:
        Dictionary of valid categories
        
    Raises:
        FileNotFoundError: If root directory doesn't exist
    """
    scanner = FileScanner()
    categories = scanner.scan_directory(root_directory, max_depth=max_depth)
    
    # Filter out categories with too few files
    return scanner.filter_categories_by_size(categories, min_files=min_files_per_category)
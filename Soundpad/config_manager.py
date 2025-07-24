"""
Configuration Manager for Soundpad Commander.

Handles loading, saving, and validation of YAML configuration files.
Manages settings, shortcuts, and category mappings.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict


@dataclass
class SoundpadSettings:
    """Soundpad application settings."""
    executable_path: str = r"C:\Program Files\Soundpad\Soundpad.exe"
    pipe_path: str = r"\\.\pipe\sp_remote_control"
    auto_launch: bool = True


@dataclass
class CategoryConfig:
    """Configuration for a sound category."""
    soundpad_category_id: int
    keyboard_shortcut: List[str]
    folder_path: str
    enabled: bool = True
    sound_count: int = 0


@dataclass
class AppSettings:
    """General application settings."""
    play_on_speakers: bool = True
    play_on_microphone: bool = True
    log_level: str = "INFO"
    show_notifications: bool = True
    auto_start_with_windows: bool = False


class ConfigManager:
    """
    Manages Soundpad Commander configuration using YAML files.
    
    Handles loading/saving configuration, validation, and provides
    convenient access to settings and category mappings.
    """
    
    DEFAULT_CONFIG_NAME = "Soundpad-config.yaml"
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize config manager.
        
        Args:
            config_path: Path to config file (defaults to current directory)
        """
        if config_path is None:
            config_path = os.path.join(os.getcwd(), self.DEFAULT_CONFIG_NAME)
        
        self.config_path = Path(config_path)
        self.config_data = {}
        self._load_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration structure."""
        return {
            'soundpad': asdict(SoundpadSettings()),
            'shortcuts': {
                'stop_playback': []
            },
            'categories': {},
            'settings': asdict(AppSettings())
        }
    
    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as file:
                    self.config_data = yaml.safe_load(file) or {}
            except (yaml.YAMLError, IOError) as e:
                print(f"Warning: Failed to load config file: {e}")
                self.config_data = {}
        else:
            self.config_data = {}
        
        # Ensure all required sections exist
        default_config = self._get_default_config()
        for key, value in default_config.items():
            if key not in self.config_data:
                self.config_data[key] = value
    
    def save_config(self) -> bool:
        """
        Save configuration to YAML file.
        
        Returns:
            True if saved successfully
        """
        try:
            # Ensure directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_path, 'w', encoding='utf-8') as file:
                yaml.dump(self.config_data, file, 
                         default_flow_style=False, 
                         allow_unicode=True,
                         sort_keys=False,
                         indent=2)
            return True
        except (yaml.YAMLError, IOError) as e:
            print(f"Error: Failed to save config file: {e}")
            return False
    
    def backup_config(self, suffix: str = ".backup") -> bool:
        """
        Create a backup copy of the current config.
        
        Args:
            suffix: Suffix to add to backup filename
            
        Returns:
            True if backup created successfully
        """
        if not self.config_path.exists():
            return False
        
        backup_path = self.config_path.with_suffix(self.config_path.suffix + suffix)
        try:
            import shutil
            shutil.copy2(self.config_path, backup_path)
            return True
        except IOError as e:
            print(f"Error: Failed to create backup: {e}")
            return False
    
    # Soundpad Settings
    
    def get_soundpad_settings(self) -> SoundpadSettings:
        """Get Soundpad application settings."""
        soundpad_config = self.config_data.get('soundpad', {})
        return SoundpadSettings(**soundpad_config)
    
    def set_soundpad_executable_path(self, path: str) -> None:
        """Set path to Soundpad executable."""
        if 'soundpad' not in self.config_data:
            self.config_data['soundpad'] = {}
        self.config_data['soundpad']['executable_path'] = path
    
    def get_soundpad_executable_path(self) -> str:
        """Get path to Soundpad executable."""
        return self.config_data.get('soundpad', {}).get(
            'executable_path', r"C:\Program Files\Soundpad\Soundpad.exe"
        )
    
    def set_auto_launch_soundpad(self, auto_launch: bool) -> None:
        """Set whether to auto-launch Soundpad."""
        if 'soundpad' not in self.config_data:
            self.config_data['soundpad'] = {}
        self.config_data['soundpad']['auto_launch'] = auto_launch
    
    # Category Management
    
    def add_category(self, name: str, soundpad_id: int, folder_path: str, 
                    shortcut: Optional[List[str]] = None) -> None:
        """
        Add a new category configuration.
        
        Args:
            name: Category name
            soundpad_id: Soundpad category ID
            folder_path: Path to folder containing sounds
            shortcut: Keyboard shortcut (optional)
        """
        if 'categories' not in self.config_data:
            self.config_data['categories'] = {}
        
        category_config = {
            'soundpad_category_id': soundpad_id,
            'keyboard_shortcut': shortcut or [],
            'folder_path': folder_path,
            'enabled': True,
            'sound_count': 0
        }
        
        self.config_data['categories'][name] = category_config
    
    def remove_category(self, name: str) -> bool:
        """
        Remove a category from configuration.
        
        Args:
            name: Category name to remove
            
        Returns:
            True if category was removed
        """
        categories = self.config_data.get('categories', {})
        if name in categories:
            del categories[name]
            return True
        return False
    
    def get_category(self, name: str) -> Optional[CategoryConfig]:
        """
        Get category configuration by name.
        
        Args:
            name: Category name
            
        Returns:
            CategoryConfig instance or None if not found
        """
        categories = self.config_data.get('categories', {})
        if name in categories:
            return CategoryConfig(**categories[name])
        return None
    
    def get_all_categories(self) -> Dict[str, CategoryConfig]:
        """
        Get all category configurations.
        
        Returns:
            Dictionary mapping category names to CategoryConfig instances
        """
        categories = self.config_data.get('categories', {})
        return {name: CategoryConfig(**config) for name, config in categories.items()}
    
    def get_enabled_categories(self) -> Dict[str, CategoryConfig]:
        """Get only enabled category configurations."""
        all_categories = self.get_all_categories()
        return {name: config for name, config in all_categories.items() if config.enabled}
    
    def update_category_shortcut(self, name: str, shortcut: List[str]) -> bool:
        """
        Update keyboard shortcut for a category.
        
        Args:
            name: Category name
            shortcut: New keyboard shortcut keys
            
        Returns:
            True if updated successfully
        """
        categories = self.config_data.get('categories', {})
        if name in categories:
            categories[name]['keyboard_shortcut'] = shortcut
            return True
        return False
    
    def update_category_sound_count(self, name: str, count: int) -> bool:
        """
        Update sound count for a category.
        
        Args:
            name: Category name
            count: Number of sounds in category
            
        Returns:
            True if updated successfully
        """
        categories = self.config_data.get('categories', {})
        if name in categories:
            categories[name]['sound_count'] = count
            return True
        return False
    
    def set_category_enabled(self, name: str, enabled: bool) -> bool:
        """
        Enable or disable a category.
        
        Args:
            name: Category name
            enabled: Whether category should be enabled
            
        Returns:
            True if updated successfully
        """
        categories = self.config_data.get('categories', {})
        if name in categories:
            categories[name]['enabled'] = enabled
            return True
        return False
    
    # Shortcut Management
    
    def get_stop_shortcut(self) -> List[str]:
        """Get pause/resume toggle keyboard shortcut."""
        return self.config_data.get('shortcuts', {}).get('stop_playback', [])
    
    def set_stop_shortcut(self, shortcut: List[str]) -> None:
        """Set pause/resume toggle keyboard shortcut."""
        if 'shortcuts' not in self.config_data:
            self.config_data['shortcuts'] = {}
        self.config_data['shortcuts']['stop_playback'] = shortcut
    
    def get_shortcut_mapping(self) -> Dict[Tuple[str, ...], str]:
        """
        Get mapping of keyboard shortcuts to category names.
        
        Returns:
            Dictionary mapping shortcut tuples to category names
        """
        shortcut_map = {}
        categories = self.get_enabled_categories()
        
        for name, config in categories.items():
            if config.keyboard_shortcut:
                shortcut_key = tuple(sorted(config.keyboard_shortcut))
                shortcut_map[shortcut_key] = name
        
        # Add pause/resume shortcut
        stop_shortcut = self.get_stop_shortcut()
        if stop_shortcut:
            shortcut_map[tuple(sorted(stop_shortcut))] = "__pause_resume__"
        
        return shortcut_map
    
    def get_conflicting_shortcuts(self) -> Dict[Tuple[str, ...], List[str]]:
        """
        Find conflicting keyboard shortcuts.
        
        Returns:
            Dictionary mapping shortcut tuples to lists of conflicting items
        """
        conflicts = defaultdict(list)
        categories = self.get_all_categories()
        
        # Check category shortcuts
        for name, config in categories.items():
            if config.keyboard_shortcut:
                shortcut_key = tuple(sorted(config.keyboard_shortcut))
                conflicts[shortcut_key].append(f"category:{name}")
        
        # Check pause/resume shortcut
        stop_shortcut = self.get_stop_shortcut()
        if stop_shortcut:
            shortcut_key = tuple(sorted(stop_shortcut))
            conflicts[shortcut_key].append("pause_resume")
        
        # Return only actual conflicts (more than one item)
        return {k: v for k, v in conflicts.items() if len(v) > 1}
    
    # Application Settings
    
    def get_app_settings(self) -> AppSettings:
        """Get general application settings."""
        settings_config = self.config_data.get('settings', {})
        return AppSettings(**settings_config)
    
    def set_app_setting(self, key: str, value: Any) -> None:
        """Set an application setting."""
        if 'settings' not in self.config_data:
            self.config_data['settings'] = {}
        self.config_data['settings'][key] = value
    
    def get_app_setting(self, key: str, default: Any = None) -> Any:
        """Get an application setting value."""
        return self.config_data.get('settings', {}).get(key, default)
    
    # Validation
    
    def validate_config(self) -> List[str]:
        """
        Validate configuration and return list of issues found.
        
        Returns:
            List of validation error messages
        """
        issues = []
        
        # Check Soundpad executable path
        soundpad_path = self.get_soundpad_executable_path()
        if soundpad_path:
            if not os.path.exists(soundpad_path):
                issues.append(f"Soundpad executable not found: {soundpad_path}")
            elif not soundpad_path.lower().endswith('.exe'):
                issues.append(f"Soundpad path should point to executable (.exe): {soundpad_path}")
            elif not os.access(soundpad_path, os.X_OK):
                issues.append(f"Soundpad executable is not executable: {soundpad_path}")
        else:
            issues.append("Soundpad executable path is not configured")
        
        # Check category folder paths and configurations
        categories = self.get_all_categories()
        for name, config in categories.items():
            # Check folder path
            if config.folder_path:
                if not os.path.exists(config.folder_path):
                    issues.append(f"Category '{name}' folder not found: {config.folder_path}")
                elif not os.path.isdir(config.folder_path):
                    issues.append(f"Category '{name}' path is not a directory: {config.folder_path}")
                elif not os.access(config.folder_path, os.R_OK):
                    issues.append(f"Category '{name}' folder is not readable: {config.folder_path}")
            else:
                issues.append(f"Category '{name}' has no folder path configured")
            
            # Check category ID
            if config.soundpad_category_id <= 0:
                issues.append(f"Category '{name}' has invalid Soundpad ID: {config.soundpad_category_id}")
            
            # Check keyboard shortcut validity
            if config.keyboard_shortcut:
                if len(config.keyboard_shortcut) == 0:
                    issues.append(f"Category '{name}' has empty keyboard shortcut")
                elif len(config.keyboard_shortcut) > 4:
                    issues.append(f"Category '{name}' has too many keys in shortcut (max 4): {len(config.keyboard_shortcut)}")
                
                # Check for invalid key names
                valid_keys = {
                    'ctrl', 'alt', 'shift', 'cmd',  # Modifiers
                    'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12',  # Function keys
                    'space', 'enter', 'tab', 'esc', 'backspace', 'delete',  # Special keys
                    'up', 'down', 'left', 'right', 'home', 'end', 'page_up', 'page_down',  # Navigation
                    'insert', 'pause', 'print_screen', 'scroll_lock', 'num_lock', 'caps_lock'  # Other special
                }
                # Add alphanumeric keys
                valid_keys.update(set('abcdefghijklmnopqrstuvwxyz0123456789'))
                
                for key in config.keyboard_shortcut:
                    if key.lower() not in valid_keys:
                        issues.append(f"Category '{name}' has invalid key in shortcut: '{key}'")
        
        # Check pause/resume shortcut
        stop_shortcut = self.get_stop_shortcut()
        if stop_shortcut:
            if len(stop_shortcut) == 0:
                issues.append("Pause/resume shortcut is configured but empty")
            elif len(stop_shortcut) > 4:
                issues.append(f"Pause/resume shortcut has too many keys (max 4): {len(stop_shortcut)}")
        
        # Check for shortcut conflicts
        conflicts = self.get_conflicting_shortcuts()
        for shortcut, conflicting_items in conflicts.items():
            shortcut_str = "+".join(sorted(shortcut))
            items_str = ", ".join(conflicting_items)
            issues.append(f"Shortcut conflict '{shortcut_str}': {items_str}")
        
        # Check for common configuration issues
        enabled_categories = self.get_enabled_categories()
        if not enabled_categories:
            issues.append("No enabled categories found - run setup tool first")
        
        categories_with_shortcuts = sum(1 for c in enabled_categories.values() if c.keyboard_shortcut)
        if categories_with_shortcuts == 0:
            issues.append("No categories have keyboard shortcuts assigned")
        
        return issues
    
    def is_first_run(self) -> bool:
        """Check if this is the first run (no config file exists)."""
        return not self.config_path.exists()
    
    def validate_file_sizes(self) -> List[str]:
        """
        Validate file sizes according to CLAUDE.md requirements.
        Check for Python files exceeding 80KB that should be split.
        
        Returns:
            List of file size issues
        """
        issues = []
        max_file_size = 80 * 1024  # 80KB as per CLAUDE.md
        
        # Check Python files in the project
        python_files = [
            'Soundpad/soundpad_client.py',
            'Soundpad/config_manager.py', 
            'Soundpad/file_scanner.py',
            'Soundpad/keyboard_listener.py',
            'bin/Soundpad-setup.py',
            'bin/Soundpad-config.py',
            'bin/Soundpad-run.py'
        ]
        
        for file_path in python_files:
            if os.path.exists(file_path):
                try:
                    file_size = os.path.getsize(file_path)
                    if file_size > max_file_size:
                        size_kb = file_size / 1024
                        issues.append(f"File '{file_path}' is {size_kb:.1f}KB (exceeds 80KB limit)")
                except OSError:
                    pass  # Skip files we can't access
        
        return issues

    def get_config_info(self) -> Dict[str, Any]:
        """Get information about the current configuration."""
        categories = self.get_all_categories()
        enabled_categories = self.get_enabled_categories()
        conflicts = self.get_conflicting_shortcuts()
        
        return {
            'config_path': str(self.config_path),
            'config_exists': self.config_path.exists(),
            'total_categories': len(categories),
            'enabled_categories': len(enabled_categories),
            'total_shortcuts': sum(1 for c in categories.values() if c.keyboard_shortcut),
            'conflicts': len(conflicts),
            'soundpad_path': self.get_soundpad_executable_path(),
            'validation_issues': self.validate_config(),
            'file_size_issues': self.validate_file_sizes()
        }


def create_default_config(config_path: Optional[str] = None) -> ConfigManager:
    """
    Create a new configuration file with default settings.
    
    Args:
        config_path: Path where config should be created
        
    Returns:
        ConfigManager instance with default configuration
    """
    config_manager = ConfigManager(config_path)
    config_manager.save_config()
    return config_manager
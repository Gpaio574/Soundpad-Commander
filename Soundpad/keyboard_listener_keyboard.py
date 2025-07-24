"""
Keyboard Listener for Soundpad Commander using the 'keyboard' library.

Provides global keyboard shortcut detection and handling for
triggering sound playbook and other Soundpad commands using the keyboard library
which has better Windows support than pynput.
"""

import time
import threading
from typing import Dict, List, Set, Callable, Optional, Tuple, Any
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum

try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False
    keyboard = None
    print("Warning: keyboard library not available. Keyboard shortcuts will not work.")

# Keep pynput for keyboard capture during configuration
try:
    from pynput import keyboard as pynput_keyboard
    from pynput.keyboard import Key, KeyCode
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    Key = None
    KeyCode = None
    pynput_keyboard = None


@dataclass
class KeyCombination:
    """Represents a keyboard shortcut combination."""
    keys: List[str]
    callback: Callable[[], None]
    description: str = ""
    enabled: bool = True
    combo_id: str = ""


class KeyboardListener:
    """
    Global keyboard listener for Soundpad Commander using the 'keyboard' library.
    
    This implementation uses the 'keyboard' library which has better Windows support
    for global hotkeys than pynput's GlobalHotKeys.
    """
    
    def __init__(self, suppress_keys: bool = False):
        """
        Initialize the keyboard listener.
        
        Args:
            suppress_keys: Whether to suppress keys after processing (not recommended for global shortcuts)
        """
        if not KEYBOARD_AVAILABLE:
            raise RuntimeError("keyboard library is required for keyboard monitoring")
        
        self.running = False
        self.suppress_keys = suppress_keys
        self.registered_combinations: Dict[str, KeyCombination] = {}
        self.hotkey_handlers: List = []  # Store keyboard hotkey handlers
        self._lock = threading.Lock()
        
        # Statistics
        self.event_count = 0
        self.last_event_time = 0.0
    
    def register_combination(self, keys: List[str], callback: Callable[[], None], 
                           combo_id: Optional[str] = None, description: str = "") -> str:
        """
        Register a key combination with a callback.
        
        Args:
            keys: List of key names (e.g., ['alt', '1'])
            callback: Function to call when combination is detected
            combo_id: Unique identifier (auto-generated if not provided)
            description: Human-readable description
            
        Returns:
            The combination ID that was registered
            
        Raises:
            ValueError: If combination is invalid or already registered
        """
        if not keys:
            raise ValueError("Key combination cannot be empty")
        
        # Generate ID if not provided
        if combo_id is None:
            combo_id = "+".join(keys)
        
        # Convert keys to keyboard library format
        hotkey_string = self._keys_to_hotkey_string(keys)
        
        with self._lock:
            if combo_id in self.registered_combinations:
                raise ValueError(f"Combination '{combo_id}' is already registered")
            
            # Create combination object
            combination = KeyCombination(
                keys=keys,
                callback=callback,
                description=description,
                enabled=True,
                combo_id=combo_id
            )
            
            # Store the combination
            self.registered_combinations[combo_id] = combination
            
            # Register with keyboard library if already running
            if self.running:
                self._register_hotkey(hotkey_string, callback)
        
        return combo_id
    
    def _keys_to_hotkey_string(self, keys: List[str]) -> str:
        """
        Convert our key format to keyboard library format.
        
        Args:
            keys: List of key names (e.g., ['alt', '1'])
            
        Returns:
            Hotkey string (e.g., 'alt+1')
        """
        hotkey_parts = []
        
        for key in keys:
            key_lower = key.lower().strip()
            
            # Handle modifier keys (keyboard library uses different names)
            if key_lower in ['ctrl', 'control']:
                hotkey_parts.append('ctrl')
            elif key_lower == 'alt':
                hotkey_parts.append('alt')
            elif key_lower == 'shift':
                hotkey_parts.append('shift')
            elif key_lower in ['cmd', 'win', 'windows']:
                hotkey_parts.append('windows')
            # Handle function keys
            elif key_lower.startswith('f') and key_lower[1:].isdigit():
                hotkey_parts.append(key_lower)
            # Handle regular keys
            else:
                hotkey_parts.append(key_lower)
        
        return '+'.join(hotkey_parts)
    
    def _register_hotkey(self, hotkey_string: str, callback: Callable):
        """Register a single hotkey with the keyboard library."""
        try:
            # Use keyboard.add_hotkey which is more reliable than GlobalHotKeys
            handler = keyboard.add_hotkey(hotkey_string, callback, suppress=self.suppress_keys)
            self.hotkey_handlers.append((hotkey_string, handler))
        except Exception as e:
            print(f"Failed to register hotkey '{hotkey_string}': {e}")
    
    def _register_all_hotkeys(self):
        """Register all enabled hotkeys with the keyboard library."""
        for combo_id, combination in self.registered_combinations.items():
            if combination.enabled:
                hotkey_string = self._keys_to_hotkey_string(combination.keys)
                self._register_hotkey(hotkey_string, combination.callback)
    
    def _unregister_all_hotkeys(self):
        """Unregister all hotkeys from the keyboard library."""
        for hotkey_string, handler in self.hotkey_handlers:
            try:
                keyboard.remove_hotkey(handler)
            except:
                pass  # Ignore errors during cleanup
        self.hotkey_handlers.clear()
    
    def unregister_combination(self, combo_id: str) -> bool:
        """
        Unregister a key combination.
        
        Args:
            combo_id: The combination ID to unregister
            
        Returns:
            True if combination was found and removed
        """
        with self._lock:
            if combo_id not in self.registered_combinations:
                return False
            
            combination = self.registered_combinations[combo_id]
            hotkey_string = self._keys_to_hotkey_string(combination.keys)
            
            # Remove from registered combinations
            del self.registered_combinations[combo_id]
            
            # Remove from keyboard library if running
            if self.running:
                # Find and remove the handler
                for i, (hs, handler) in enumerate(self.hotkey_handlers):
                    if hs == hotkey_string:
                        try:
                            keyboard.remove_hotkey(handler)
                            del self.hotkey_handlers[i]
                        except:
                            pass
                        break
        
        return True
    
    def enable_combination(self, combo_id: str) -> bool:
        """Enable a registered combination."""
        with self._lock:
            if combo_id not in self.registered_combinations:
                return False
            
            combination = self.registered_combinations[combo_id]
            if not combination.enabled:
                combination.enabled = True
                
                if self.running:
                    hotkey_string = self._keys_to_hotkey_string(combination.keys)
                    self._register_hotkey(hotkey_string, combination.callback)
        
        return True
    
    def disable_combination(self, combo_id: str) -> bool:
        """Disable a registered combination."""
        with self._lock:
            if combo_id not in self.registered_combinations:
                return False
            
            combination = self.registered_combinations[combo_id]
            if combination.enabled:
                combination.enabled = False
                
                if self.running:
                    hotkey_string = self._keys_to_hotkey_string(combination.keys)
                    # Find and remove the handler
                    for i, (hs, handler) in enumerate(self.hotkey_handlers):
                        if hs == hotkey_string:
                            try:
                                keyboard.remove_hotkey(handler)
                                del self.hotkey_handlers[i]
                            except:
                                pass
                            break
        
        return True
    
    def start(self) -> None:
        """
        Start the keyboard listener.
        
        Raises:
            RuntimeError: If listener is already running
        """
        if self.running:
            raise RuntimeError("Keyboard listener is already running")
        
        if not self.registered_combinations:
            print("Warning: No hotkeys registered, listener will do nothing")
        
        try:
            # Register all hotkeys with the keyboard library
            self._register_all_hotkeys()
            self.running = True
            
        except Exception as e:
            raise RuntimeError(f"Failed to start keyboard listener: {e}")
    
    def stop(self) -> None:
        """Stop the keyboard listener."""
        if not self.running:
            return
        
        self.running = False
        
        # Unregister all hotkeys
        self._unregister_all_hotkeys()
    
    def is_running(self) -> bool:
        """Check if the keyboard listener is currently running."""
        return self.running
    
    def get_registered_combinations(self) -> Dict[str, KeyCombination]:
        """Get all registered key combinations."""
        with self._lock:
            return self.registered_combinations.copy()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get listener statistics."""
        with self._lock:
            return {
                'running': self.running,
                'registered_combinations': len(self.registered_combinations),
                'enabled_combinations': sum(1 for c in self.registered_combinations.values() if c.enabled),
                'active_handlers': len(self.hotkey_handlers)
            }
    
    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()


class KeyboardCapture:
    """
    Utility class for capturing keyboard input during shortcut configuration.
    
    This still uses pynput for configuration capture since it's more suitable
    for interactive key capture than the keyboard library.
    """
    
    def __init__(self):
        """Initialize keyboard capture."""
        if not PYNPUT_AVAILABLE:
            raise RuntimeError("pynput library is required for keyboard capture")
        
        self.listener = None
        self.captured_keys: Set[str] = set()
        self.capture_active = False
        self._lock = threading.Lock()
        
        # Initialize special keys mapping
        self.SPECIAL_KEYS = self._init_special_keys()
    
    def _init_special_keys(self):
        """Initialize special keys mapping (only if pynput is available)."""
        if not PYNPUT_AVAILABLE or Key is None:
            return {}
        
        return {
            Key.ctrl_l: 'ctrl', Key.ctrl_r: 'ctrl',
            Key.alt_l: 'alt', Key.alt_r: 'alt',
            Key.shift: 'shift', Key.shift_l: 'shift', Key.shift_r: 'shift',
            Key.cmd: 'cmd', Key.cmd_l: 'cmd', Key.cmd_r: 'cmd',
            Key.f1: 'f1', Key.f2: 'f2', Key.f3: 'f3', Key.f4: 'f4',
            Key.f5: 'f5', Key.f6: 'f6', Key.f7: 'f7', Key.f8: 'f8',
            Key.f9: 'f9', Key.f10: 'f10', Key.f11: 'f11', Key.f12: 'f12',
            Key.space: 'space', Key.enter: 'enter', Key.tab: 'tab',
            Key.esc: 'esc', Key.backspace: 'backspace', Key.delete: 'delete',
            Key.home: 'home', Key.end: 'end', Key.page_up: 'page_up',
            Key.page_down: 'page_down', Key.up: 'up', Key.down: 'down',
            Key.left: 'left', Key.right: 'right', Key.insert: 'insert',
            Key.pause: 'pause', Key.print_screen: 'print_screen',
            Key.scroll_lock: 'scroll_lock', Key.num_lock: 'num_lock',
            Key.caps_lock: 'caps_lock'
        }
    
    def _normalize_key_name(self, key) -> Optional[str]:
        """
        Normalize a pynput key to a string name.
        
        Args:
            key: pynput Key or KeyCode object
            
        Returns:
            Normalized key name or None if not recognized
        """
        if key in self.SPECIAL_KEYS:
            return self.SPECIAL_KEYS[key]
        elif hasattr(key, 'char') and key.char:
            # Regular character key
            return key.char.lower()
        elif hasattr(key, 'vk') and key.vk:
            # Virtual key code - try to convert to char
            try:
                char = chr(key.vk).lower()
                if char.isalnum():
                    return char
            except ValueError:
                pass
        
        return None
    
    def _on_key_press(self, key) -> None:
        """Handle key press during capture."""
        if not self.capture_active:
            return
        
        key_name = self._normalize_key_name(key)
        
        if key_name:
            with self._lock:
                self.captured_keys.add(key_name)
    
    def _on_key_release(self, key) -> None:
        """Handle key release during capture."""
        pass  # We only care about what keys are pressed together
    
    def start_capture(self, timeout: Optional[float] = None) -> Set[str]:
        """
        Start capturing keyboard input.
        
        Args:
            timeout: Maximum time to wait for input (seconds)
            
        Returns:
            Set of captured key names
        """
        self.captured_keys.clear()
        self.capture_active = True
        
        # Start listener
        self.listener = pynput_keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release
        )
        self.listener.start()
        
        # Wait for Enter key or timeout
        start_time = time.time()
        while self.capture_active:
            if timeout and (time.time() - start_time) > timeout:
                break
            
            with self._lock:
                if 'enter' in self.captured_keys:
                    # Remove Enter key from results
                    self.captured_keys.discard('enter')
                    break
            
            time.sleep(0.01)  # Small delay to prevent busy waiting
        
        self.stop_capture()
        return self.captured_keys.copy()
    
    def stop_capture(self) -> None:
        """Stop capturing keyboard input."""
        self.capture_active = False
        
        if self.listener:
            self.listener.stop()
            self.listener = None


def normalize_key_combination(keys: List[str]) -> List[str]:
    """
    Normalize a list of key names to standard format.
    
    Args:
        keys: List of key names to normalize
        
    Returns:
        Normalized and sorted list of key names
    """
    normalized = []
    for key in keys:
        key = key.lower().strip()
        
        # Handle common aliases
        key_aliases = {
            'control': 'ctrl',
            'ctrl_l': 'ctrl',
            'ctrl_r': 'ctrl',
            'alt_l': 'alt', 
            'alt_r': 'alt',
            'shift_l': 'shift',
            'shift_r': 'shift',
            'cmd_l': 'cmd',
            'cmd_r': 'cmd',
            'windows': 'cmd',
            'win': 'cmd'
        }
        
        key = key_aliases.get(key, key)
        
        if key and key not in normalized:
            normalized.append(key)
    
    # Sort with modifiers first for consistent ordering
    modifier_order = ['ctrl', 'alt', 'shift', 'cmd']
    
    # Separate modifiers from other keys
    modifiers = []
    other_keys = []
    
    for key in normalized:
        if key.lower() in modifier_order:
            modifiers.append(key.lower())
        else:
            other_keys.append(key)
    
    # Sort modifiers by predefined order
    sorted_modifiers = []
    for mod in modifier_order:
        if mod in modifiers:
            sorted_modifiers.append(mod)
    
    # Combine modifiers first, then other keys sorted alphabetically
    return sorted_modifiers + sorted(other_keys)


def key_combination_to_string(keys: List[str]) -> str:
    """
    Convert a key combination to a human-readable string.
    
    Args:
        keys: List of key names
        
    Returns:
        Human-readable string (e.g., "Alt+1", "Ctrl+Alt+F1")
    """
    if not keys:
        return ""
    
    # Define modifier key order (modifiers should come first)
    modifier_order = ['ctrl', 'alt', 'shift', 'cmd']
    
    # Separate modifiers from other keys
    modifiers = []
    other_keys = []
    
    for key in keys:
        if key.lower() in modifier_order:
            modifiers.append(key.lower())
        else:
            other_keys.append(key)
    
    # Sort modifiers by predefined order
    sorted_modifiers = []
    for mod in modifier_order:
        if mod in modifiers:
            sorted_modifiers.append(mod)
    
    # Format all keys
    formatted_keys = []
    
    # Add modifiers first
    for key in sorted_modifiers:
        if key == 'ctrl':
            formatted_keys.append('Ctrl')
        elif key == 'alt':
            formatted_keys.append('Alt')
        elif key == 'shift':
            formatted_keys.append('Shift')
        elif key == 'cmd':
            formatted_keys.append('Win')
    
    # Add other keys
    for key in sorted(other_keys):  # Sort non-modifiers alphabetically
        if key.startswith('f') and key[1:].isdigit():
            formatted_keys.append(key.upper())  # F1, F2, etc.
        else:
            formatted_keys.append(key.capitalize())
    
    return '+'.join(formatted_keys)
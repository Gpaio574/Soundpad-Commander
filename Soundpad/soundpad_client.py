"""
Soundpad API Client - Python wrapper for Soundpad's Named Pipe API.

This module provides a Python interface to communicate with Soundpad using
Windows Named Pipes, replicating the functionality of the Java reference implementation.
"""

import os
import time
import json
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum


class PlayStatus(Enum):
    """Soundpad playback status enumeration."""
    STOPPED = "STOPPED"
    PLAYING = "PLAYING"
    PAUSED = "PAUSED"
    SEEKING = "SEEKING"


class SoundpadClient:
    """
    Python client for communicating with Soundpad via Named Pipes.
    
    This client replicates the functionality of the Java SoundpadRemoteControl class,
    allowing Python applications to control Soundpad remotely.
    """
    
    CLIENT_VERSION = "1.1.2"
    PIPE_PATH = r"\\.\pipe\sp_remote_control"
    
    def __init__(self, print_errors: bool = True):
        """
        Initialize the Soundpad client.
        
        Args:
            print_errors: Whether to print error messages to console
        """
        self.print_errors = print_errors
        self.pipe = None
        self.last_request_timestamp = time.time()
    
    def init(self) -> None:
        """
        Initialize connection to Soundpad's named pipe.
        
        Raises:
            FileNotFoundError: If Soundpad is not running or pipe is unavailable
            PermissionError: If insufficient permissions to access pipe
        """
        if self.pipe is None:
            try:
                # Open named pipe in read/write binary mode
                # O_BINARY is Windows-specific, use it only if available
                flags = os.O_RDWR
                if hasattr(os, 'O_BINARY'):
                    flags |= os.O_BINARY
                self.pipe = os.open(self.PIPE_PATH, flags)
            except FileNotFoundError:
                raise FileNotFoundError(
                    "Cannot connect to Soundpad. Make sure Soundpad is running and the remote control interface is enabled."
                )
            except PermissionError:
                raise PermissionError(
                    "Permission denied accessing Soundpad pipe. Try running as administrator or check Windows security settings."
                )
            except OSError as e:
                if e.errno == 2:  # No such file or directory
                    raise FileNotFoundError(
                        "Soundpad named pipe not found. Ensure Soundpad is running and remote control is enabled."
                    )
                elif e.errno == 13:  # Permission denied
                    raise PermissionError(
                        f"Access denied to Soundpad pipe. Error code: {e.errno}. Try running as administrator."
                    )
                elif e.errno == 32:  # File in use by another process
                    raise OSError(
                        "Soundpad pipe is busy. Another application may be using the remote control interface."
                    )
                else:
                    raise OSError(
                        f"Failed to open Soundpad pipe. Windows error code: {e.errno}. {e.strerror}"
                    )
    
    def uninit(self) -> None:
        """Close the connection to Soundpad's named pipe."""
        if self.pipe is not None:
            try:
                os.close(self.pipe)
            except OSError:
                pass  # Ignore errors when closing
            finally:
                self.pipe = None
    
    def send_request(self, request: str) -> str:
        """
        Send a command to Soundpad and return the response.
        
        Args:
            request: Command string to send to Soundpad
            
        Returns:
            Response string from Soundpad (e.g., "R-200" for success)
            
        Raises:
            OSError: If communication with Soundpad fails
        """
        self.init()
        
        # Prevent too many requests at the same time (from Java reference)
        current_time = time.time()
        if abs(current_time - self.last_request_timestamp) < 0.001:
            time.sleep(0.001)  # Sleep 1ms to prevent pipe breakage
        
        try:
            # Write request to pipe
            request_bytes = request.encode('utf-8')
            os.write(self.pipe, request_bytes)
            
            # Read response following Java reference protocol:
            # "data size in pipe is first acquirable after reading one byte"
            first_byte = os.read(self.pipe, 1)
            if not first_byte:
                raise OSError("No response from Soundpad")
            
            # Get remaining data length and read full response
            # Using a reasonable buffer size for the remaining data
            remaining_data = os.read(self.pipe, 8192)  # Increased buffer size
            
            # Combine first byte with remaining data
            response_bytes = first_byte + remaining_data
            response = response_bytes.decode('utf-8').rstrip('\0')  # Remove null terminators
            
            self.last_request_timestamp = time.time()
            return response
            
        except OSError as e:
            self.uninit()  # Close pipe on error
            raise OSError(f"Failed to communicate with Soundpad: {e}")
    
    def send_request_safe(self, request: str) -> str:
        """
        Send request with error handling - returns empty string on failure.
        
        Args:
            request: Command string to send to Soundpad
            
        Returns:
            Response string or empty string if communication fails
        """
        try:
            return self.send_request(request)
        except (OSError, FileNotFoundError, PermissionError) as e:
            if self.print_errors:
                print(f"Soundpad communication error: {e}")
            self.uninit()
            return ""
    
    def _print_error(self, message: str) -> None:
        """Print error message if error printing is enabled."""
        if self.print_errors:
            print(f"Soundpad Error: {message}")
    
    def _is_success(self, response: str) -> bool:
        """Check if response indicates success."""
        return response.startswith("R-200")
    
    def _handle_error_response(self, response: str, command: str = "") -> str:
        """
        Handle and interpret error responses from Soundpad.
        
        Args:
            response: Response from Soundpad
            command: Original command that caused the error
            
        Returns:
            Human-readable error message
        """
        if not response:
            return "No response from Soundpad"
        
        if response.startswith("R-"):
            error_code = response[:5]  # e.g., "R-404"
            
            # Common HTTP-style error codes from Soundpad
            error_messages = {
                "R-400": "Bad Request - Invalid command format",
                "R-404": "Not Found - Invalid sound/category index",
                "R-403": "Forbidden - Command not allowed in trial version",
                "R-500": "Internal Server Error - Soundpad error",
                "R-503": "Service Unavailable - Soundpad busy"
            }
            
            if error_code in error_messages:
                base_msg = error_messages[error_code]
                if "trial" in response.lower():
                    base_msg += " (Trial version limitation)"
                return f"{base_msg}: {response}"
            else:
                return f"Soundpad error {error_code}: {response}"
        
        return f"Unexpected response: {response}"
    
    def _handle_numeric_response(self, request: str) -> int:
        """Handle requests that return numeric values."""
        response = self.send_request_safe(request)
        if not response:
            self._print_error("No response from Soundpad")
            return -1
        
        if response.startswith("R"):
            error_msg = self._handle_error_response(response, request)
            self._print_error(error_msg)
            return -1
        
        try:
            return int(response)
        except ValueError:
            self._print_error(f"Expected numeric response, got: {response}")
            return -1
    
    def _handle_string_response(self, request: str) -> str:
        """Handle requests that return string values."""
        response = self.send_request_safe(request)
        if not response:
            self._print_error("No response from Soundpad")
            return ""
        
        if response.startswith("R"):
            error_msg = self._handle_error_response(response, request)
            self._print_error(error_msg)
            return ""
        
        return response
    
    # Core Playback Methods
    
    def play_sound(self, index: int, speakers: bool = True, microphone: bool = True) -> bool:
        """
        Play a sound by its index in the "All sounds" category.
        
        Args:
            index: Sound index (1-based)
            speakers: Play on speakers (render line)
            microphone: Play on microphone (capture line)
            
        Returns:
            True if successful
        """
        if speakers is True and microphone is True:
            # Simple version without explicit audio routing
            request = f"DoPlaySound({index})"
        else:
            # Explicit audio routing
            request = f"DoPlaySound({index}, {str(speakers).lower()}, {str(microphone).lower()})"
        
        response = self.send_request_safe(request)
        return self._is_success(response)
    
    def play_sound_from_category(self, category_index: int, sound_index: int, 
                                speakers: bool = True, microphone: bool = True) -> bool:
        """
        Play a specific sound from a category.
        
        Args:
            category_index: Category index (-1 for currently selected)
            sound_index: Sound position within category (1-based)
            speakers: Play on speakers
            microphone: Play on microphone
            
        Returns:
            True if successful
        """
        request = f"DoPlaySoundFromCategory({category_index}, {sound_index}, {str(speakers).lower()}, {str(microphone).lower()})"
        response = self.send_request_safe(request)
        return self._is_success(response)
    
    def play_random_sound_from_category(self, category_index: int,
                                      speakers: bool = True, microphone: bool = True) -> bool:
        """
        Play a random sound from the specified category.
        
        Args:
            category_index: Category index (-1 for currently selected)
            speakers: Play on speakers
            microphone: Play on microphone
            
        Returns:
            True if successful
        """
        request = f"DoPlayRandomSoundFromCategory({category_index}, {str(speakers).lower()}, {str(microphone).lower()})"
        response = self.send_request_safe(request)
        return self._is_success(response)
    
    def play_random_sound(self, speakers: bool = True, microphone: bool = True) -> bool:
        """
        Play a random sound from any category.
        
        Args:
            speakers: Play on speakers
            microphone: Play on microphone
            
        Returns:
            True if successful
        """
        request = f"DoPlayRandomSound({str(speakers).lower()}, {str(microphone).lower()})"
        response = self.send_request_safe(request)
        return self._is_success(response)
    
    def stop_sound(self) -> bool:
        """Stop currently playing sound."""
        response = self.send_request_safe("DoStopSound()")
        return self._is_success(response)
    
    def toggle_pause(self) -> bool:
        """Toggle pause/resume of current sound."""
        response = self.send_request_safe("DoTogglePause()")
        return self._is_success(response)
    
    def play_previous_sound(self) -> bool:
        """Play the previous sound in the list."""
        response = self.send_request_safe("DoPlayPreviousSound()")
        return self._is_success(response)
    
    def play_next_sound(self) -> bool:
        """Play the next sound in the list."""
        response = self.send_request_safe("DoPlayNextSound()")
        return self._is_success(response)
    
    def play_selected_sound(self) -> bool:
        """Play the currently selected sound."""
        response = self.send_request_safe("DoPlaySelectedSound()")
        return self._is_success(response)
    
    def play_current_sound_again(self) -> bool:
        """Play the current sound again."""
        response = self.send_request_safe("DoPlayCurrentSoundAgain()")
        return self._is_success(response)
    
    def play_previously_played_sound(self) -> bool:
        """Play the previously played sound."""
        response = self.send_request_safe("DoPlayPreviouslyPlayedSound()")
        return self._is_success(response)
    
    # Sound Management Methods
    
    def add_sound(self, file_path: str, category_index: Optional[int] = None, 
                  position: Optional[int] = None) -> bool:
        """
        Add a sound file to Soundpad.
        
        Args:
            file_path: Full path to audio file
            category_index: Category to add to (optional)
            position: Position within category (optional)
            
        Returns:
            True if successful
        """
        if category_index is not None and position is not None:
            request = f'DoAddSound("{file_path}", {category_index}, {position})'
        elif category_index is not None:
            request = f'DoAddSound("{file_path}", {category_index})'
        else:
            request = f'DoAddSound("{file_path}")'
        
        response = self.send_request_safe(request)
        success = self._is_success(response)
        
        if not success and response:
            error_msg = self._handle_error_response(response, request)
            self._print_error(f"Failed to add sound '{file_path}': {error_msg}")
        
        return success
    
    # Category Management Methods
    
    def add_category(self, name: str, parent_index: int = -1) -> bool:
        """
        Add a new category to Soundpad.
        
        Args:
            name: Category name
            parent_index: Parent category index (-1 for root)
            
        Returns:
            True if successful
        """
        request = f'DoAddCategory("{name}", {parent_index})'
        response = self.send_request_safe(request)
        success = self._is_success(response)
        
        if not success and response:
            error_msg = self._handle_error_response(response, request)
            self._print_error(f"Failed to add category '{name}': {error_msg}")
        
        return success
    
    def select_category(self, category_index: int) -> bool:
        """
        Select a category by its index.
        
        Args:
            category_index: Category index to select
            
        Returns:
            True if successful
        """
        request = f"DoSelectCategory({category_index})"
        response = self.send_request_safe(request)
        return self._is_success(response)
    
    def remove_category(self, category_index: int) -> bool:
        """
        Remove a category by its index.
        
        Args:
            category_index: Category index to remove
            
        Returns:
            True if successful
        """
        request = f"DoRemoveCategory({category_index})"
        response = self.send_request_safe(request)
        success = self._is_success(response)
        
        if not success and response:
            error_msg = self._handle_error_response(response, request)
            self._print_error(f"Failed to remove category (ID {category_index}): {error_msg}")
        
        return success
    
    def get_categories(self, with_sounds: bool = False, with_icons: bool = False) -> str:
        """
        Get category tree as XML.
        
        Args:
            with_sounds: Include sound entries in response
            with_icons: Include base64 encoded icons
            
        Returns:
            XML formatted category list
        """
        request = f"GetCategories({str(with_sounds).lower()}, {str(with_icons).lower()})"
        return self._handle_string_response(request)
    
    def get_category(self, category_index: int, with_sounds: bool = False, 
                    with_icons: bool = False) -> str:
        """
        Get specific category information as XML.
        
        Args:
            category_index: Category index to retrieve
            with_sounds: Include sound entries
            with_icons: Include base64 encoded icon
            
        Returns:
            XML formatted category information
        """
        request = f"GetCategory({category_index}, {str(with_sounds).lower()}, {str(with_icons).lower()})"
        return self._handle_string_response(request)
    
    # Information Methods
    
    def get_sound_file_count(self) -> int:
        """Get total number of sound files."""
        return self._handle_numeric_response("GetSoundFileCount()")
    
    def get_soundlist(self, from_index: Optional[int] = None, to_index: Optional[int] = None) -> str:
        """
        Get sound list as XML from the "All sounds" category.
        
        Args:
            from_index: Start index (optional)
            to_index: End index (optional)
            
        Returns:
            XML formatted sound list
        """
        if from_index is not None and to_index is not None:
            request = f"GetSoundlist({from_index}, {to_index})"
        elif from_index is not None:
            request = f"GetSoundlist({from_index})"
        else:
            request = "GetSoundlist()"
        
        return self._handle_string_response(request)
    
    def get_play_status(self) -> PlayStatus:
        """Get current playback status."""
        response = self.send_request_safe("GetPlayStatus()")
        
        if response.startswith("R"):
            self._print_error(f"Failed to get play status: {response}")
            return PlayStatus.STOPPED
        
        try:
            return PlayStatus(response)
        except ValueError:
            self._print_error(f"Unknown play status: {response}")
            return PlayStatus.STOPPED
    
    def get_version(self) -> str:
        """Get Soundpad version."""
        return self._handle_string_response("GetVersion()")
    
    def get_remote_control_version(self) -> str:
        """Get remote control interface version."""
        return self._handle_string_response("GetRemoteControlVersion()")
    
    def is_compatible(self) -> bool:
        """Check if client version matches Soundpad's remote control version."""
        return self.CLIENT_VERSION == self.get_remote_control_version()
    
    def is_alive(self) -> bool:
        """Check if Soundpad is running and accessible."""
        response = self.send_request_safe("IsAlive()")
        return self._is_success(response)
    
    def is_trial(self) -> bool:
        """Check if Soundpad is running in trial mode."""
        response = self.send_request_safe("IsTrial()")
        if not response or response.startswith("R"):
            return False
        
        try:
            return int(response) == 1
        except ValueError:
            return False
    
    # Volume and Audio Methods
    
    def get_volume(self) -> int:
        """Get speaker volume (0-100)."""
        return max(0, self._handle_numeric_response("GetVolume()"))
    
    def set_volume(self, volume: int) -> bool:
        """
        Set speaker volume.
        
        Args:
            volume: Volume level (0-100)
            
        Returns:
            True if successful
        """
        volume = max(0, min(100, volume))  # Clamp to valid range
        response = self.send_request_safe(f"SetVolume({volume})")
        return self._is_success(response)
    
    def is_muted(self) -> bool:
        """Check if speakers are muted."""
        response = self.send_request_safe("IsMuted()")
        if not response or response.startswith("R"):
            return False
        
        try:
            return int(response) == 1
        except ValueError:
            return False
    
    def toggle_mute(self) -> bool:
        """Toggle mute state of speakers."""
        response = self.send_request_safe("DoToggleMute()")
        return self._is_success(response)
    
    # Recording Methods
    
    def start_recording(self) -> bool:
        """
        Start recording. This call is handled the same way as if a recording is
        started by hotkeys, which means a notification sound is played.
        
        Returns:
            True if recording was started or was already running
        """
        response = self.send_request_safe("DoStartRecording()")
        return self._is_success(response)
    
    def stop_recording(self) -> bool:
        """Stop recording."""
        response = self.send_request_safe("DoStopRecording()")
        return self._is_success(response)
    
    def start_recording_speakers(self) -> bool:
        """
        Start recording of the speakers. Method might fail if the microphone is
        currently being recorded.
        
        Returns:
            True if recording was started or was already running
        """
        response = self.send_request_safe("DoStartRecordingSpeakers()")
        success = self._is_success(response)
        if not success and response:
            self._print_error(f"Failed to start speaker recording: {response}")
        return success
    
    def start_recording_microphone(self) -> bool:
        """
        Start recording of the microphone. Method might fail if the speakers are
        currently being recorded.
        
        Returns:
            True if recording was started or was already running  
        """
        response = self.send_request_safe("DoStartRecordingMicrophone()")
        success = self._is_success(response)
        if not success and response:
            self._print_error(f"Failed to start microphone recording: {response}")
        return success
    
    def get_recording_position(self) -> int:
        """Get recording position in milliseconds."""
        return max(0, self._handle_numeric_response("GetRecordingPositionInMs()"))
    
    def get_recording_peak(self) -> int:
        """Get current recording peak level."""
        return max(0, self._handle_numeric_response("GetRecordingPeak()"))
    
    # Utility Methods
    
    def __enter__(self):
        """Context manager entry."""
        self.init()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.uninit()


# Convenience function for basic usage
def create_client(print_errors: bool = True) -> SoundpadClient:
    """
    Create and return a new SoundpadClient instance.
    
    Args:
        print_errors: Whether to print error messages
        
    Returns:
        SoundpadClient instance
    """
    return SoundpadClient(print_errors=print_errors)
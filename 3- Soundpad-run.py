#!/usr/bin/env python3
"""
Soundpad Commander Runtime

Main application that listens for global keyboard shortcuts and
triggers sound playback through Soundpad.
"""

import sys
import os
import time
import signal
import subprocess
import ctypes
from pathlib import Path
from typing import Dict, List, Optional, Set
from datetime import datetime
from dataclasses import dataclass

# Add current directory to path for imports (scripts now in root)
sys.path.insert(0, os.path.dirname(__file__))

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.layout import Layout
    from rich.align import Align
    from rich.text import Text
    from rich.live import Live
    from rich.status import Status
    import questionary
    from questionary import Style
except ImportError as e:
    print(f"Error: Required packages not installed. Run: pip install -r requirements.txt")
    print(f"Missing: {e}")
    sys.exit(1)

try:
    from Soundpad.soundpad_client import SoundpadClient, create_client
    from Soundpad.config_manager import ConfigManager, CategoryConfig
    from Soundpad.keyboard_listener import KeyboardListener, key_combination_to_string
except ImportError as e:
    print(f"Error: Could not import Soundpad modules: {e}")
    print("Make sure you're running from the correct directory.")
    sys.exit(1)


def is_admin() -> bool:
    """
    Check if the current process has administrator privileges.
    
    Returns:
        True if running as administrator, False otherwise
    """
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def run_as_admin() -> bool:
    """
    Re-launch the current script with administrator privileges.
    
    Returns:
        True if elevation was attempted, False if it failed
    """
    try:
        # Get the current script path
        script_path = sys.argv[0]
        params = ' '.join(sys.argv[1:]) if len(sys.argv) > 1 else ''
        
        # Request elevation using ShellExecute with 'runas'
        result = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            sys.executable,
            f'"{script_path}" {params}',
            None,
            1  # SW_SHOWNORMAL
        )
        
        # ShellExecute returns a value > 32 for success
        return result > 32
    except Exception as e:
        print(f"Failed to elevate privileges: {e}")
        return False


@dataclass
class ActionLog:
    """Log entry for performed actions."""
    timestamp: datetime
    action: str
    category: Optional[str] = None
    success: bool = True
    details: str = ""


class SoundpadRuntime:
    """Main runtime application for Soundpad Commander."""
    
    def __init__(self):
        """Initialize the runtime application."""
        self.console = Console()
        self.config_manager = None
        self.soundpad_client = None
        self.keyboard_listener = None
        
        # Runtime state
        self.running = False
        self.soundpad_connected = False
        self.shortcuts_loaded = 0
        self.action_log: List[ActionLog] = []
        self.stats = {
            'sounds_played': 0,
            'pauses_triggered': 0,  # Renamed from stops_triggered for clarity
            'errors': 0,
            'start_time': None,
            'last_action': None
        }
        
        # Signal handling
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        self.console.print("\n[yellow]Shutting down...[/yellow]")
        self.stop()
        sys.exit(0)
    
    def print_header(self) -> None:
        """Print the application header."""
        header = Panel(
            Align.center(
                Text("SOUNDPAD COMMANDER\nRUNTIME MODE", style="bold cyan"),
                vertical="middle"
            ),
            style="cyan",
            height=7
        )
        self.console.print(header)
    
    def init_config(self) -> bool:
        """Initialize configuration manager."""
        try:
            self.console.print("[dim]Initializing configuration manager...[/dim]")
            self.config_manager = ConfigManager()
            
            # Validate configuration
            issues = self.config_manager.validate_config()
            if issues:
                self.console.print("[yellow]WARNING Configuration Issues:[/yellow]")
                for issue in issues:
                    self.console.print(f"  [dim]- {issue}[/dim]")
                self.console.print()
            
            self.console.print("[green]OK Configuration loaded successfully[/green]")
            return True
        except Exception as e:
            self.console.print(f"[red]Error initializing configuration: {e}[/red]")
            import traceback
            self.console.print(f"[red]Traceback: {traceback.format_exc()}[/red]")
            try:
                input("\nPress Enter to continue...")
            except EOFError:
                pass
            return False
    
    def launch_soundpad_if_needed(self) -> bool:
        """Launch Soundpad if auto-launch is enabled and it's not running."""
        soundpad_settings = self.config_manager.get_soundpad_settings()
        
        if not soundpad_settings.auto_launch:
            return True
        
        # Check if Soundpad is already running
        if self._is_soundpad_running():
            return True
        
        soundpad_path = soundpad_settings.executable_path
        
        # Validate executable path
        if not self._validate_soundpad_executable(soundpad_path):
            return False
        
        # Launch Soundpad
        return self._launch_soundpad_process(soundpad_path)
    
    def _is_soundpad_running(self) -> bool:
        """Check if Soundpad is already running."""
        try:
            client = create_client(print_errors=False)
            return client.is_alive()
        except Exception:
            return False
    
    def _validate_soundpad_executable(self, soundpad_path: str) -> bool:
        """Validate that the Soundpad executable exists and is accessible."""
        if not os.path.exists(soundpad_path):
            self.console.print(f"[red]ERROR Soundpad not found: {soundpad_path}[/red]")
            self.console.print("[dim]Configure the path using Soundpad-setup.py[/dim]")
            return False
        
        if not os.access(soundpad_path, os.X_OK):
            if os.path.exists(soundpad_path):
                self.console.print(f"[red]ERROR Soundpad executable is not executable: {soundpad_path}[/red]")
                self.console.print("[dim]Check file permissions or try running as administrator[/dim]")
            else:
                self.console.print(f"[red]ERROR Soundpad executable not found: {soundpad_path}[/red]")
            return False
        
        return True
    
    def _launch_soundpad_process(self, soundpad_path: str) -> bool:
        """Launch the Soundpad process and wait for it to start."""
        try:
            self.console.print("[cyan]Launching Soundpad...[/cyan]")
            
            # Use PowerShell Start-Process (same as Windows native launch)
            subprocess.run([
                'powershell', '-Command', 
                f'Start-Process -FilePath "{soundpad_path}" -WindowStyle Normal'
            ], 
            shell=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False
            )
            
            # Wait for Soundpad to start
            return self._wait_for_soundpad_startup()
            
        except OSError as e:
            self.console.print(f"[red]ERROR Failed to launch Soundpad: {e}[/red]")
            try:
                input("\nPress Enter to continue...")
            except EOFError:
                pass
            return False
        except OSError as e:
            self._handle_launch_os_error(e, soundpad_path)
            return False
        except Exception as e:
            self.console.print(f"[red]ERROR Unexpected error launching Soundpad: {e}[/red]")
            return False
    
    
    def _wait_for_soundpad_startup(self) -> bool:
        """Wait for Soundpad to start and become available."""
        max_wait = 10  # seconds
        for i in range(max_wait):
            time.sleep(1)
            try:
                client = create_client(print_errors=False)
                if client.is_alive():
                    self.console.print("[green]✓ Soundpad launched successfully[/green]")
                    return True
            except Exception:
                pass
            
            self.console.print(f"\r[dim]Waiting for Soundpad to start... {i+1}/{max_wait}[/dim]", end="")
        
        self.console.print("\n[yellow]WARNING Soundpad launched but remote control interface not available[/yellow]")
        self.console.print("[dim]Make sure remote control is enabled in Soundpad settings[/dim]")
        return False
    
    def _handle_launch_os_error(self, e: OSError, soundpad_path: str) -> None:
        """Handle OS errors during Soundpad launch."""
        error_messages = {
            2: f"ERROR Soundpad executable not found: {soundpad_path}",
            13: "ERROR Permission denied launching Soundpad. Try running as administrator."
        }
        
        if e.errno in error_messages:
            self.console.print(f"[red]{error_messages[e.errno]}[/red]")
        else:
            self.console.print(f"[red]ERROR OS error launching Soundpad (code {e.errno}): {e.strerror}[/red]")
    
    def connect_to_soundpad(self, retry_count=0) -> bool:
        """Connect to Soundpad API."""
        # Prevent infinite retry loop
        if retry_count >= 2:
            self.soundpad_connected = False
            return False
            
        try:
            self.soundpad_client = create_client()
            if self.soundpad_client.is_alive():
                self.soundpad_connected = True
                return True
            else:
                self.soundpad_connected = False
                self.console.print("[yellow]WARNING Soundpad is not running[/yellow]")
                # Try to auto-launch Soundpad if configured (only on first attempt)
                if retry_count == 0 and self._try_auto_launch_soundpad():
                    return self.connect_to_soundpad(retry_count + 1)  # Retry connection once
                return False
        except Exception as e:
            self.soundpad_connected = False
            self.console.print(f"[red]Soundpad communication error: Cannot connect to Soundpad. Make sure Soundpad is running and the remote control interface is enabled.[/red]")
            # Try to auto-launch Soundpad if configured (only on first attempt)
            if retry_count == 0 and self._try_auto_launch_soundpad():
                return self.connect_to_soundpad(retry_count + 1)  # Retry connection once
            return False
    
    def setup_keyboard_shortcuts(self) -> bool:
        """Set up global keyboard shortcuts."""
        if not self.config_manager:
            return False
        
        try:
            self.keyboard_listener = KeyboardListener()
            self.log_action("debug", None, True, "KeyboardListener created")
            
            # Register category shortcuts
            categories = self.config_manager.get_enabled_categories()
            for name, config in categories.items():
                if config.keyboard_shortcut:
                    callback = self.create_category_callback(name, config)
                    combo_id = self.keyboard_listener.register_combination(
                        keys=config.keyboard_shortcut,
                        callback=callback,
                        combo_id=f"category_{name}",
                        description=f"Play random sound from {name}"
                    )
                    shortcut_str = key_combination_to_string(config.keyboard_shortcut)
                    # Get the actual hotkey string that will be used by pynput
                    hotkey_str = self.keyboard_listener._keys_to_hotkey_string(config.keyboard_shortcut)
                    self.log_action("debug", None, True, f"Registered {shortcut_str} -> '{hotkey_str}' for '{name}'")
                    self.shortcuts_loaded += 1
            
            # Register pause/resume shortcut
            pause_resume_shortcut = self.config_manager.get_stop_shortcut()
            if pause_resume_shortcut:
                callback = self.create_pause_callback()
                combo_id = self.keyboard_listener.register_combination(
                    keys=pause_resume_shortcut,
                    callback=callback,
                    combo_id="pause_resume",
                    description="Toggle pause/resume"
                )
                shortcut_str = key_combination_to_string(pause_resume_shortcut)
                # Get the actual hotkey string that will be used by keyboard library
                hotkey_str = self.keyboard_listener._keys_to_hotkey_string(pause_resume_shortcut)
                self.log_action("debug", None, True, f"Registered pause/resume {shortcut_str} -> '{hotkey_str}'")
                self.shortcuts_loaded += 1
            
            return True
        
        except Exception as e:
            self.console.print(f"[red]Error setting up shortcuts: {e}[/red]")
            self.log_action("debug", None, False, f"Error setting up shortcuts: {e}")
            try:
                input("\nPress Enter to continue...")
            except EOFError:
                pass
            return False
    
    def create_category_callback(self, category_name: str, config: CategoryConfig):
        """Create callback function for a category shortcut."""
        def callback():
            # Debug: Log that callback was triggered
            self.log_action("debug", category_name, True, f"Shortcut triggered for '{category_name}'")
            
            if not self.soundpad_client or not self.soundpad_connected:
                self.log_action("play_failed", category_name, False, "Not connected to Soundpad")
                return
            
            try:
                # Get app settings for audio routing
                app_settings = self.config_manager.get_app_settings()
                success = self.soundpad_client.play_random_sound_from_category(
                    config.soundpad_category_id,
                    speakers=app_settings.play_on_speakers,
                    microphone=app_settings.play_on_microphone
                )
                
                if success:
                    self.stats['sounds_played'] += 1
                    self.stats['last_action'] = f"Played from '{category_name}'"
                    self.log_action("play_sound", category_name, True)
                else:
                    self.stats['errors'] += 1
                    self.log_action("play_failed", category_name, False, "Soundpad command failed")
                    
            except Exception as e:
                self.stats['errors'] += 1
                self.log_action("play_failed", category_name, False, str(e))
        
        return callback
    
    def create_pause_callback(self):
        """Create callback function for pause/resume shortcut."""
        def callback():
            # Debug: Log that pause/resume callback was triggered
            self.log_action("debug", None, True, "Pause/resume shortcut triggered")
            
            if not self.soundpad_client or not self.soundpad_connected:
                self.log_action("pause_failed", None, False, "Not connected to Soundpad")
                return
            
            try:
                # Get current play status before toggling
                current_status = self.soundpad_client.get_play_status()
                success = self.soundpad_client.toggle_pause()
                
                if success:
                    self.stats['pauses_triggered'] += 1
                    
                    # Determine what action was performed based on previous state
                    if current_status.value == "PLAYING":
                        self.stats['last_action'] = "Paused sound"
                        self.log_action("pause_sound", None, True)
                    elif current_status.value == "PAUSED":
                        self.stats['last_action'] = "Resumed sound"
                        self.log_action("resume_sound", None, True)
                    else:
                        # For other states (STOPPED, SEEKING), just show generic toggle
                        self.stats['last_action'] = "Toggled pause/resume"
                        self.log_action("toggle_pause", None, True)
                else:
                    self.stats['errors'] += 1
                    self.log_action("pause_failed", None, False, "Soundpad command failed")
                    
            except Exception as e:
                self.stats['errors'] += 1
                self.log_action("pause_failed", None, False, str(e))
        
        return callback
    
    def log_action(self, action: str, category: Optional[str], success: bool, details: str = ""):
        """Log an action for display and debugging."""
        log_entry = ActionLog(
            timestamp=datetime.now(),
            action=action,
            category=category,
            success=success,
            details=details
        )
        
        self.action_log.append(log_entry)
        
        # Keep only recent entries
        if len(self.action_log) > 50:
            self.action_log = self.action_log[-50:]
    
    def create_status_layout(self) -> Layout:
        """Create the live status display layout."""
        # Calculate dynamic size for shortcuts panel based on actual shortcuts count
        shortcuts_size = self._calculate_shortcuts_panel_size()
        
        layout = Layout()
        layout.split_column(
            Layout(name="status", size=12),
            Layout(name="shortcuts", size=shortcuts_size),
            Layout(name="activity")
        )
        
        return layout
    
    def _calculate_shortcuts_panel_size(self) -> int:
        """Calculate appropriate size for shortcuts panel based on number of shortcuts."""
        if not self.config_manager:
            return 8  # Minimum size for "Configuration not loaded" message
        
        # Count actual shortcuts
        categories = self.config_manager.get_enabled_categories()
        stop_shortcut = self.config_manager.get_stop_shortcut()
        
        shortcut_count = 0
        
        # Count pause/resume shortcut
        if stop_shortcut:
            shortcut_count += 1
        
        # Count category shortcuts
        for config in categories.values():
            if config.keyboard_shortcut:
                shortcut_count += 1
        
        if shortcut_count == 0:
            return 6  # Size for "No shortcuts configured" message
        
        # Add space for title (2 lines) + border (2 lines) + padding (1 line) + shortcuts
        # Each shortcut takes 1 line, minimum 8 for reasonable display
        return max(8, shortcut_count + 5)
    
    def update_status_panel(self, layout: Layout) -> None:
        """Update the status panel."""
        # Connection status
        soundpad_status = "[green]* Connected[/green]" if self.soundpad_connected else "[red]* Disconnected[/red]"
        runtime_status = "[green]* Running[/green]" if self.running else "[red]* Stopped[/red]"
        
        # Uptime
        if self.stats['start_time']:
            uptime = datetime.now() - self.stats['start_time']
            uptime_str = f"{int(uptime.total_seconds())}s"
        else:
            uptime_str = "0s"
        
        # Last action
        last_action = self.stats.get('last_action', 'None')
        
        status_content = f"""[bold]Status:[/bold] {runtime_status}
[bold]Soundpad:[/bold] {soundpad_status}
[bold]Shortcuts:[/bold] {self.shortcuts_loaded} loaded
[bold]Uptime:[/bold] {uptime_str}
[bold]Sounds Played:[/bold] {self.stats['sounds_played']}
[bold]Pauses:[/bold] {self.stats['pauses_triggered']}
[bold]Errors:[/bold] {self.stats['errors']}
[bold]Last Action:[/bold] {last_action}"""
        
        status_panel = Panel(
            status_content,
            title="Soundpad Commander",
            border_style="cyan"
        )
        
        layout["status"].update(status_panel)
    
    def update_shortcuts_panel(self, layout: Layout) -> None:
        """Update the shortcuts panel."""
        if not self.config_manager:
            layout["shortcuts"].update(Panel("[red]Configuration not loaded[/red]", title="Shortcuts"))
            return
        
        # Get shortcuts
        categories = self.config_manager.get_enabled_categories()
        pause_resume_shortcut = self.config_manager.get_stop_shortcut()
        
        shortcuts_text = ""
        shortcut_count = 0
        
        # Pause/Resume shortcut
        if pause_resume_shortcut:
            combo_str = key_combination_to_string(pause_resume_shortcut)
            shortcuts_text += f"[yellow]{combo_str}[/yellow] - Pause/Resume\n"
            shortcut_count += 1
        
        # Category shortcuts
        for name, config in categories.items():
            if config.keyboard_shortcut:
                combo_str = key_combination_to_string(config.keyboard_shortcut)
                shortcuts_text += f"[green]{combo_str}[/green] - {name}\n"
                shortcut_count += 1
        
        if not shortcuts_text:
            shortcuts_text = "[dim]No shortcuts configured[/dim]"
        
        # Add shortcut count to title for debugging
        title = f"Active Shortcuts ({shortcut_count} total)"
        
        shortcuts_panel = Panel(
            shortcuts_text.strip(),
            title=title,
            border_style="green"
        )
        
        layout["shortcuts"].update(shortcuts_panel)
    
    def update_activity_panel(self, layout: Layout) -> None:
        """Update the activity log panel."""
        if not self.action_log:
            activity_text = "[dim]No activity yet...[/dim]"
        else:
            # Show recent actions
            recent_actions = self.action_log[-10:]  # Last 10 actions
            activity_lines = []
            
            for log_entry in reversed(recent_actions):
                time_str = log_entry.timestamp.strftime("%H:%M:%S")
                
                if log_entry.action == "play_sound":
                    icon = "▶️" if log_entry.success else "❌"
                    text = f"{icon} Played from '{log_entry.category}'"
                elif log_entry.action == "pause_sound":
                    icon = "⏸️" if log_entry.success else "❌"
                    text = f"{icon} Paused sound"
                elif log_entry.action == "resume_sound":
                    icon = "▶️" if log_entry.success else "❌"
                    text = f"{icon} Resumed sound"
                elif log_entry.action == "toggle_pause":
                    icon = "⏯️" if log_entry.success else "❌"
                    text = f"{icon} Toggled pause/resume"
                elif log_entry.action == "stop_sound":  # Keep for backwards compatibility
                    icon = "⏹️" if log_entry.success else "❌"
                    text = f"{icon} Stopped sound"
                elif log_entry.action == "debug":
                    icon = "🐛"
                    text = f"{icon} DEBUG: {log_entry.details}"
                elif log_entry.action.endswith("_failed"):
                    icon = "❌"
                    text = f"{icon} Failed: {log_entry.details}"
                else:
                    icon = "▶️"
                    text = f"{icon} {log_entry.action}"
                
                activity_lines.append(f"[dim]{time_str}[/dim] {text}")
            
            activity_text = "\n".join(activity_lines)
        
        activity_panel = Panel(
            activity_text,
            title="Activity Log",
            border_style="blue"
        )
        
        layout["activity"].update(activity_panel)
    
    def monitor_soundpad_connection(self) -> None:
        """Monitor Soundpad connection and attempt reconnection."""
        if not self.soundpad_client:
            return
        
        try:
            is_alive = self.soundpad_client.is_alive()
            if is_alive and not self.soundpad_connected:
                self.soundpad_connected = True
                self.log_action("reconnected", None, True, "Soundpad connection restored")
            elif not is_alive and self.soundpad_connected:
                self.soundpad_connected = False
                self.log_action("disconnected", None, False, "Lost connection to Soundpad")
        except:
            if self.soundpad_connected:
                self.soundpad_connected = False
                self.log_action("disconnected", None, False, "Connection error")
    
    def run_interactive_mode(self) -> None:
        """Run in interactive mode with live status display."""
        self.console.print("\n[cyan]Starting interactive mode...[/cyan]")
        self.console.print("[dim]Press Ctrl+C to stop[/dim]\n")
        
        layout = self.create_status_layout()
        
        with Live(layout, refresh_per_second=2, screen=True) as live:
            while self.running:
                try:
                    # Update all panels
                    self.update_status_panel(layout)
                    self.update_shortcuts_panel(layout)
                    self.update_activity_panel(layout)
                    
                    # Monitor Soundpad connection periodically
                    self.monitor_soundpad_connection()
                    
                    # Sleep briefly
                    time.sleep(0.5)
                    
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    self.log_action("error", None, False, f"Runtime error: {e}")
                    time.sleep(1)
    
    def run_background_mode(self) -> None:
        """Run in background mode (minimal output)."""
        self.console.print("[cyan]Running in background mode...[/cyan]")
        self.console.print("[dim]Soundpad Commander is active. Press Ctrl+C to stop.[/dim]")
        
        try:
            while self.running:
                # Monitor connection periodically
                self.monitor_soundpad_connection()
                time.sleep(5)  # Check every 5 seconds
                
        except KeyboardInterrupt:
            pass
    
    def start(self, interactive: bool = True) -> bool:
        """
        Start the runtime application.
        
        Args:
            interactive: Whether to show interactive status display
            
        Returns:
            True if started successfully
        """
        self.console.print("[dim]Starting Soundpad Commander...[/dim]")
        self.stats['start_time'] = datetime.now()
        
        # Initialize configuration
        self.console.print("[dim]Step 1: Initializing configuration...[/dim]")
        if not self.init_config():
            self.console.print("[red]Failed to initialize configuration[/red]")
            return False
        
        # Launch Soundpad if needed
        if not self.launch_soundpad_if_needed():
            try:
                if not questionary.confirm("Continue without Soundpad?").ask():
                    return False
            except (EOFError, KeyboardInterrupt, Exception):
                # Non-interactive mode - continue without Soundpad
                self.console.print("[yellow]Running in non-interactive mode, continuing without Soundpad...[/yellow]")
        
        # Connect to Soundpad
        if not self.connect_to_soundpad():
            self.console.print("[yellow]WARNING Starting without Soundpad connection[/yellow]")
        
        # Set up keyboard shortcuts
        if not self.setup_keyboard_shortcuts():
            return False
        
        if self.shortcuts_loaded == 0:
            self.console.print("[yellow]WARNING No shortcuts configured[/yellow]")
            self.console.print("[dim]Run Soundpad-config.py to set up shortcuts[/dim]")
        
        # Start keyboard listener
        try:
            self.log_action("debug", None, True, "Starting keyboard listener...")
            self.keyboard_listener.start()
            self.running = True
            
            self.log_action("started", None, True, f"Loaded {self.shortcuts_loaded} shortcuts")
            self.log_action("debug", None, True, "Keyboard listener started successfully")
            
            if interactive:
                self.run_interactive_mode()
            else:
                self.run_background_mode()
            
            return True
            
        except Exception as e:
            self.console.print(f"[red]Failed to start keyboard listener: {e}[/red]")
            self.log_action("debug", None, False, f"Failed to start keyboard listener: {e}")
            try:
                input("\nPress Enter to continue...")
            except EOFError:
                pass
            return False
    
    def stop(self) -> None:
        """Stop the runtime application."""
        self.running = False
        
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        
        if self.soundpad_client:
            self.soundpad_client.uninit()
        
        self.log_action("stopped", None, True, "Application shutdown")
    
    def show_startup_menu(self) -> bool:
        """Show startup options menu."""
        self.console.print()
        self.console.print("[dim]Entering show_startup_menu...[/dim]")
        
        # Initialize configuration first
        if not self.init_config():
            self.console.print("[red]Failed to initialize configuration[/red]")
            return False
        
        # Check configuration status
        if not self.config_manager:
            self.console.print("[red]Configuration manager not initialized[/red]")
            return False
        
        categories = self.config_manager.get_enabled_categories()
        shortcuts_count = sum(1 for c in categories.values() if c.keyboard_shortcut)
        
        if shortcuts_count == 0:
            self.console.print("[yellow]WARNING No shortcuts configured![/yellow]")
            self.console.print("[dim]Run Soundpad-config.py to set up keyboard shortcuts first.[/dim]")
            
            try:
                choice = questionary.select(
                    "What would you like to do?",
                    choices=[
                        "Continue anyway",
                        "Exit and configure shortcuts"
                    ]
                ).ask()
                
                if choice == "Exit and configure shortcuts":
                    return False
            except (EOFError, KeyboardInterrupt, Exception):
                # Non-interactive mode - continue anyway
                self.console.print("[yellow]Running in non-interactive mode, continuing anyway...[/yellow]")
        
        # Start directly in interactive mode
        self.console.print("[cyan]Starting in Interactive mode with live status...[/cyan]")
        return self.start(interactive=True)
    
    def run(self) -> None:
        """Main entry point."""
        # Check for administrator privileges
        if not is_admin():
            self.console.print("[yellow]Administrator privileges required for global keyboard shortcuts.[/yellow]")
            self.console.print("[dim]Attempting to restart with administrator privileges...[/dim]")
            
            if run_as_admin():
                # Successfully requested elevation, exit current process
                sys.exit(0)
            else:
                self.console.print("[red]Failed to obtain administrator privileges.[/red]")
                self.console.print("[yellow]Global keyboard shortcuts may not work properly.[/yellow]")
                self.console.print("[cyan]The application will still start, but shortcuts might not work.[/cyan]")
                self.console.print("[dim]Press Ctrl+C to exit or wait 3 seconds to continue...[/dim]")
                try:
                    time.sleep(3)
                except KeyboardInterrupt:
                    sys.exit(0)
        else:
            self.console.print("[green]Running with administrator privileges.[/green]")
        
        self.print_header()
        
        try:
            success = self.show_startup_menu()
            if not success:
                self.console.print("\n[yellow]Startup cancelled or failed[/yellow]")
                try:
                    input("\nPress Enter to exit...")
                except EOFError:
                    pass
        
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Interrupted by user[/yellow]")
        except Exception as e:
            self.console.print(f"\n[red]Unexpected error: {e}[/red]")
            try:
                input("\nPress Enter to continue...")
            except EOFError:
                pass
        
        finally:
            self.stop()
            self.console.print("\n[green]Soundpad Commander stopped[/green]")
            try:
                input("\nPress Enter to exit...")
            except EOFError:
                pass
    
    def _try_auto_launch_soundpad(self) -> bool:
        """Try to auto-launch Soundpad if configured to do so."""
        if not self.config_manager:
            return False
        
        soundpad_settings = self.config_manager.get_soundpad_settings()
        
        if not soundpad_settings.auto_launch:
            return False
        
        soundpad_path = soundpad_settings.executable_path
        
        # Validate executable path
        if not os.path.exists(soundpad_path):
            self.console.print(f"[red]ERROR Soundpad executable not found: {soundpad_path}[/red]")
            return False
        
        # Launch Soundpad using CMD (same as running from command prompt)
        try:
            self.console.print("[cyan]Launching Soundpad...[/cyan]")
            import subprocess
            import time
            
            # Use PowerShell Start-Process (same as Windows native launch)
            subprocess.run([
                'powershell', '-Command', 
                f'Start-Process -FilePath "{soundpad_path}" -WindowStyle Normal'
            ], 
            shell=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False
            )
            
            # Wait for Soundpad to start
            for attempt in range(10):  # Wait up to 10 seconds
                time.sleep(1)
                try:
                    test_client = create_client()
                    if test_client.is_alive():
                        self.console.print("[green]OK Soundpad launched successfully[/green]")
                        return True
                except:
                    pass
            
            self.console.print("[yellow]WARNING Soundpad launched but not responding yet. Please wait a moment and try again.[/yellow]")
            return False
            
        except Exception as e:
            self.console.print(f"[red]ERROR Failed to launch Soundpad: {e}[/red]")
            try:
                input("\nPress Enter to continue...")
            except EOFError:
                pass
            return False


if __name__ == "__main__":
    runtime = SoundpadRuntime()
    runtime.run()
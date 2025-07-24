#!/usr/bin/env python3
"""
Soundpad Commander Configuration Tool

Interactive CLI tool for configuring keyboard shortcuts and testing
Soundpad integration functionality.
"""

import sys
import os
import time
import threading
from pathlib import Path
from typing import Dict, List, Optional, Set

# Add current directory to path for imports (scripts now in root)
sys.path.insert(0, os.path.dirname(__file__))

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.prompt import Prompt, Confirm
    from rich.layout import Layout
    from rich.align import Align
    from rich.text import Text
    from rich.live import Live
    import questionary
    from questionary import Style
    import keyboard
except ImportError as e:
    print(f"Error: Required packages not installed. Run: pip install -r requirements.txt")
    print(f"Missing: {e}")
    sys.exit(1)

try:
    from Soundpad.soundpad_client import SoundpadClient, create_client
    from Soundpad.config_manager import ConfigManager, CategoryConfig
    from Soundpad.keyboard_listener import KeyboardCapture, normalize_key_combination, key_combination_to_string
except ImportError as e:
    print(f"Error: Could not import Soundpad modules: {e}")
    print("Make sure you're running from the correct directory.")
    sys.exit(1)


class SoundpadConfig:
    """Configuration tool for Soundpad Commander keyboard shortcuts."""
    
    def __init__(self):
        """Initialize the configuration tool."""
        self.console = Console()
        self.config_manager = None
        self.soundpad_client = None
        
        # Custom questionary style
        self.style = Style([
            ('qmark', 'fg:#ff9d00 bold'),
            ('question', 'bold'),
            ('answer', 'fg:#ff9d00 bold'),
            ('pointer', 'fg:#ff9d00 bold'),
            ('highlighted', 'fg:#ff9d00 bold'),
            ('selected', 'fg:#cc5454'),
            ('separator', 'fg:#cc5454'),
            ('instruction', ''),
            ('text', ''),
            ('disabled', 'fg:#858585 italic')
        ])
    
    def print_header(self) -> None:
        """Print the application header."""
        header = Panel(
            Align.center(
                Text("SOUNDPAD COMMANDER\nCONFIG TOOL", style="bold green"),
                vertical="middle"
            ),
            style="green",
            height=7
        )
        self.console.print(header)
        self.console.print()
    
    def init_config(self) -> bool:
        """Initialize configuration manager."""
        try:
            self.config_manager = ConfigManager()
            return True
        except Exception as e:
            self.console.print(f"[red]Error initializing configuration: {e}[/red]")
            try:
                input("\nPress Enter to continue...")
            except (KeyboardInterrupt, EOFError):
                pass
            return False
    
    def connect_to_soundpad(self, retry_count=0) -> bool:
        """Attempt to connect to Soundpad."""
        # Prevent infinite retry loop
        if retry_count >= 2:
            return False
            
        try:
            self.soundpad_client = create_client()
            if self.soundpad_client.is_alive():
                version = self.soundpad_client.get_version()
                self.console.print(f"[green]Connected to Soundpad {version}[/green]")
                return True
            else:
                self.console.print("[yellow]Warning: Soundpad is not running[/yellow]")
                # Try to auto-launch Soundpad if configured (only on first attempt)
                if retry_count == 0 and self._try_auto_launch_soundpad():
                    return self.connect_to_soundpad(retry_count + 1)  # Retry connection once
                return False
        except Exception as e:
            self.console.print(f"[red]Soundpad communication error: Cannot connect to Soundpad. Make sure Soundpad is running and the remote control interface is enabled.[/red]")
            # Try to auto-launch Soundpad if configured (only on first attempt)
            if retry_count == 0 and self._try_auto_launch_soundpad():
                return self.connect_to_soundpad(retry_count + 1)  # Retry connection once
            return False
    
    def view_current_shortcuts(self) -> None:
        """Display current keyboard shortcuts."""
        self.console.print("\n[bold]⌨️ Current Shortcuts[/bold]")
        
        if not self.config_manager:
            self.console.print("[red]✗ Configuration not initialized[/red]")
            return
        
        categories = self.config_manager.get_all_categories()
        stop_shortcut = self.config_manager.get_stop_shortcut()
        
        table = Table(show_header=True, header_style="bold green")
        table.add_column("Function", style="cyan", no_wrap=True)
        table.add_column("Shortcut", justify="center")
        table.add_column("Status")
        table.add_column("Description", style="dim")
        
        # Add pause/resume shortcut
        if stop_shortcut:
            table.add_row(
                "Pause/Resume Toggle",
                key_combination_to_string(stop_shortcut),
                "[green]Active[/green]",
                "Pause/resume currently playing sound"
            )
        else:
            table.add_row(
                "Pause/Resume Toggle", 
                "[dim]None[/dim]",
                "[red]✗ Not set[/red]",
                "Pause/resume currently playing sound"
            )
        
        table.add_section()
        
        # Add category shortcuts
        if not categories:
            table.add_row("[dim]No categories configured[/dim]", "", "", "")
        else:
            for name, config in categories.items():
                if config.keyboard_shortcut:
                    shortcut_str = key_combination_to_string(config.keyboard_shortcut)
                    status = "[green]Active[/green]" if config.enabled else "[yellow]Disabled[/yellow]"
                else:
                    shortcut_str = "[dim]None[/dim]"
                    status = "[red]✗ Not set[/red]"
                
                description = f"Play random sound from '{name}' ({config.sound_count} sounds)"
                table.add_row(name, shortcut_str, status, description)
        
        self.console.print(table)
        
        # Check for conflicts
        conflicts = self.config_manager.get_conflicting_shortcuts()
        if conflicts:
            self.console.print("\n[red]Warning: Shortcut Conflicts Found:[/red]")
            for shortcut, items in conflicts.items():
                shortcut_str = key_combination_to_string(list(shortcut))
                items_str = ", ".join(items)
                self.console.print(f"  [red]{shortcut_str}:[/red] {items_str}")
        
        self.console.print()
    
    def capture_keyboard_shortcut(self, description: str = "shortcut") -> Optional[List[str]]:
        """
        Capture a keyboard shortcut interactively.
        
        Args:
            description: Description of what the shortcut is for
            
        Returns:
            List of normalized key names or None if cancelled
        """
        self.console.print(f"\n[bold]⌨️ Capture {description}[/bold]")
        self.console.print("[cyan]Instructions:[/cyan]")
        self.console.print("  • Hold down your desired key combination") 
        self.console.print("  • Press [green]Enter[/green] to confirm")
        self.console.print("  • Press [yellow]Esc[/yellow] to clear and restart")
        self.console.print("\n[dim]Keys pressed will be shown in real-time below:[/dim]")
        self.console.print()
        
        captured_keys = set()
        display_keys = set()
        capture_active = True
        modifier_count = 0
        keys_currently_pressed = set()  # Track which keys are currently held
        last_display_content = ""  # Track last display content to avoid duplicates
        
        def on_key_event(event):
            nonlocal captured_keys, display_keys, capture_active, modifier_count, keys_currently_pressed, last_display_content
            
            if not capture_active:
                return
            
            # Get key name
            key_name = event.name.lower()
            
            # Enhanced key mappings to support all keyboard keys
            key_mappings = {
                # Modifier keys
                'ctrl': 'ctrl', 'left ctrl': 'ctrl', 'right ctrl': 'ctrl', 'control': 'ctrl',
                'alt': 'alt', 'left alt': 'alt', 'right alt': 'alt', 'menu': 'alt', 'altgr': 'alt',
                'shift': 'shift', 'left shift': 'shift', 'right shift': 'shift',
                'windows': 'cmd', 'left windows': 'cmd', 'right windows': 'cmd', 'win': 'cmd', 'cmd': 'cmd',
                
                # Lock keys
                'caps lock': 'caps_lock', 'num lock': 'num_lock', 'scroll lock': 'scroll_lock',
                
                # Navigation keys
                'page up': 'page_up', 'page down': 'page_down', 'print screen': 'print_screen',
                'insert': 'insert', 'delete': 'delete', 'home': 'home', 'end': 'end',
                
                # Arrow keys
                'up': 'up', 'down': 'down', 'left': 'left', 'right': 'right',
                
                # Function keys (F1-F24)
                **{f'f{i}': f'f{i}' for i in range(1, 25)},
                
                # Numpad keys
                **{f'num {i}': f'num_{i}' for i in range(10)},
                'num +': 'num_plus', 'num -': 'num_minus', 'num *': 'num_multiply', 
                'num /': 'num_divide', 'num .': 'num_decimal', 'num enter': 'num_enter',
                
                # Special characters and symbols
                'space': 'space', 'tab': 'tab', 'enter': 'enter', 'backspace': 'backspace',
                'escape': 'esc', 'esc': 'esc',
                
                # Punctuation (common international layouts)
                ';': 'semicolon', ':': 'colon', "'": 'apostrophe', '"': 'quote',
                ',': 'comma', '.': 'period', '/': 'slash', '?': 'question',
                '[': 'left_bracket', ']': 'right_bracket', '{': 'left_brace', '}': 'right_brace',
                '\\': 'backslash', '|': 'pipe', '`': 'grave', '~': 'tilde',
                '!': 'exclamation', '@': 'at', '#': 'hash', '$': 'dollar',
                '%': 'percent', '^': 'caret', '&': 'ampersand', '*': 'asterisk',
                '(': 'left_paren', ')': 'right_paren', '-': 'minus', '_': 'underscore',
                '=': 'equals', '+': 'plus', '<': 'less_than', '>': 'greater_than'
            }
            
            normalized_key = key_mappings.get(key_name, key_name)
            
            if event.event_type == keyboard.KEY_DOWN:
                # Skip if this key is already being held (prevents repeat events)
                if normalized_key in keys_currently_pressed:
                    return
                
                keys_currently_pressed.add(normalized_key)
                
                if normalized_key == 'enter':
                    if captured_keys:  # Only confirm if we have keys
                        capture_active = False
                        return
                elif normalized_key == 'esc':
                    captured_keys.clear()
                    display_keys.clear()
                    keys_currently_pressed.clear()
                    modifier_count = 0
                    clear_text = "Cleared - try again..."
                    print(f"\r{' ' * 120}\r{clear_text}", end="", flush=True)
                    time.sleep(0.5)  # Brief pause to show the cleared message
                    print(f"\r{' ' * 120}\r", end="", flush=True)
                    last_display_content = ""
                    return
                
                # Add key to captured set
                if normalized_key not in captured_keys:
                    captured_keys.add(normalized_key)
                    display_keys.add(normalized_key)
                    
                    # Count modifiers for validation
                    if normalized_key in ['ctrl', 'alt', 'shift', 'cmd']:
                        modifier_count += 1
                
                # Update display only if content changed
                update_key_display(display_keys, modifier_count)
            
            elif event.event_type == keyboard.KEY_UP:
                # Remove from currently pressed keys
                keys_currently_pressed.discard(normalized_key)
                
                # Only update display when all keys are released and we have captured keys
                if not keys_currently_pressed and display_keys:
                    combo_str = key_combination_to_string(sorted(display_keys))
                    held_text = f"Holding: {combo_str} (press Enter to confirm, Esc to clear)"
                    
                    # Only update if content changed
                    if held_text != last_display_content:
                        # Simple clear and print
                        print(f"\r{' ' * 120}\r{held_text}", end="", flush=True)
                        last_display_content = held_text
        
        def update_key_display(display_keys_set, mod_count):
            nonlocal last_display_content
            
            if display_keys_set:
                combo_str = key_combination_to_string(sorted(display_keys_set))
                
                # Add validation hints with better feedback
                hints = []
                status_text = ""
                if len(display_keys_set) > 4:
                    status_text = "too many keys (max 4)"
                elif mod_count == 0 and len(display_keys_set) > 1:
                    status_text = "consider adding modifier (Ctrl/Alt/Shift)"
                elif len(display_keys_set) >= 2:
                    status_text = "good combination"
                elif len(display_keys_set) == 1:
                    last_key = list(display_keys_set)[0]
                    if last_key in ['ctrl', 'alt', 'shift', 'cmd']:
                        status_text = "modifier key - add another key"
                    else:
                        status_text = "single key - consider adding modifier"
                
                # Simple display without complex formatting
                display_text = f"⌨️  Current: {combo_str} {status_text}"
                
                # Only update if content actually changed
                if display_text != last_display_content:
                    # Clear the entire line and print new content
                    print(f"\r{' ' * 120}\r{display_text}", end="", flush=True)
                    last_display_content = display_text
            else:
                # Show waiting message when no keys are pressed
                waiting_text = "Waiting for key combination..."
                if waiting_text != last_display_content:
                    print(f"\r{' ' * 120}\r{waiting_text}", end="", flush=True)
                    last_display_content = waiting_text
        
        try:
            # Start keyboard hook
            keyboard.hook(on_key_event)
            
            # Wait for completion
            while capture_active:
                try:
                    time.sleep(0.01)
                except KeyboardInterrupt:
                    # Ignore KeyboardInterrupt during capture
                    continue
            
            # Clear the input line
            print(f"\r{' ' * 120}\r", end="", flush=True)
            
            if not captured_keys:
                self.console.print("[yellow]Cancelled - no keys captured[/yellow]")
                return None
            
            # Validate combination before returning
            if len(captured_keys) > 4:
                self.console.print("[red]✗ Too many keys in combination (max 4)[/red]")
                return None
            
            modifiers = [k for k in captured_keys if k in ['ctrl', 'alt', 'shift', 'cmd']]
            if not modifiers:
                try:
                    confirm = questionary.confirm(
                        "No modifier keys detected. This may interfere with normal typing. Continue?"
                    ).ask()
                    if not confirm:
                        return None
                except KeyboardInterrupt:
                    self.console.print("\n[yellow]Operation cancelled[/yellow]")
                    return None
                except Exception as e:
                    self.console.print(f"\n[yellow]Confirmation cancelled: {e}[/yellow]")
                    return None
            
            # Normalize and return keys
            normalized = normalize_key_combination(list(captured_keys))
            combo_str = key_combination_to_string(normalized)
            self.console.print(f"[green]Captured: {combo_str}[/green]")
            
            return normalized
            
        except KeyboardInterrupt:
            print(f"\r{' ' * 120}\r", end="", flush=True)
            self.console.print("[yellow]Capture cancelled[/yellow]")
            return None
        except Exception as e:
            print(f"\r{' ' * 120}\r", end="", flush=True)
            self.console.print(f"\n[red]Error capturing shortcut: {e}[/red]")
            import traceback
            self.console.print(f"[dim]Debug: {traceback.format_exc()}[/dim]")
            try:
                input("\nPress Enter to continue...")
            except (KeyboardInterrupt, EOFError):
                pass
            return None
        finally:
            # Ensure keyboard hooks are always cleaned up
            try:
                keyboard.unhook_all()
            except Exception:
                pass  # Ignore cleanup errors
    
    def assign_category_shortcuts(self) -> None:
        """Assign keyboard shortcuts to categories."""
        while True:
            self.console.print("\n[bold]🎯 Assign Category Shortcuts[/bold]")
            
            if not self.config_manager:
                self.console.print("[red]✗ Configuration not initialized[/red]")
                return
            
            categories = self.config_manager.get_all_categories()
            if not categories:
                self.console.print("[dim]No categories available. Run Soundpad-setup.py first.[/dim]")
                return
            
            # Select category to configure or handle all
            selected_option = self._select_category_or_bulk_option(categories)
            if not selected_option:
                return
            
            if selected_option == "__handle_all__":
                self._handle_all_categories_in_order(categories)
                return
            elif selected_option == "__go_back__":
                return
            else:
                # Handle single category
                category_config = categories[selected_option]
                self._show_current_shortcut(category_config)
                
                new_shortcut = self.capture_keyboard_shortcut(f"shortcut for '{selected_option}'")
                if not new_shortcut:
                    continue
                
                # Check for conflicts and save
                if self._check_shortcut_conflicts(selected_option, new_shortcut):
                    self._save_category_shortcut(selected_option, new_shortcut)
                
                # Ask if user wants to continue configuring other categories
                try:
                    if not questionary.confirm("Configure another category?").ask():
                        return
                except Exception:
                    # Fallback for terminal compatibility issues
                    try:
                        response = input("Configure another category? [y/n]: ").lower().strip()
                        if response not in ['y', 'yes']:
                            return
                    except:
                        return
    
    def _select_category_or_bulk_option(self, categories: Dict[str, CategoryConfig]) -> Optional[str]:
        """Select category for shortcut assignment or bulk options."""
        choices = []
        
        # Add bulk handling option at the top
        choices.append(questionary.Choice(
            "🔄 Handle all categories in order",
            value="__handle_all__"
        ))
        
        choices.append(questionary.Choice("---", disabled=True))
        
        # Add individual categories
        for name, config in categories.items():
            shortcut_display = key_combination_to_string(config.keyboard_shortcut) if config.keyboard_shortcut else "No shortcut"
            choices.append(questionary.Choice(
                f"{name} ({config.sound_count} sounds) - {shortcut_display}",
                value=name
            ))
        
        choices.append(questionary.Choice("---", disabled=True))
        
        # Add go back option at the end
        choices.append(questionary.Choice(
            "← Go back to main menu",
            value="__go_back__"
        ))
        
        try:
            return questionary.select(
                "Select option:",
                choices=choices,
                style=self.style
            ).ask()
        except Exception as e:
            # Fallback for terminal compatibility issues
            self.console.print(f"[yellow]Menu display issue: {str(e)[:50]}...[/yellow]")
            self.console.print("[dim]Available options:[/dim]")
            
            option_map = {}
            for i, choice in enumerate(choices, 1):
                if not choice.disabled:
                    option_map[str(i)] = choice.value
                    self.console.print(f"  {i}. {choice.title}")
            
            while True:
                try:
                    choice_input = input("\nSelect option (number or 'q' to go back): ").strip()
                    if choice_input.lower() == 'q':
                        return "__go_back__"
                    if choice_input in option_map:
                        return option_map[choice_input]
                    self.console.print("[red]Invalid choice. Try again.[/red]")
                except KeyboardInterrupt:
                    return "__go_back__"
                except:
                    return "__go_back__"
    
    def _handle_all_categories_in_order(self, categories: Dict[str, CategoryConfig]) -> None:
        """Handle all categories in order, allowing user to assign shortcuts sequentially."""
        self.console.print("\n[bold cyan]🔄 Handling All Categories in Order[/bold cyan]")
        self.console.print("[dim]You'll be prompted to set shortcuts for each category in sequence.[/dim]")
        self.console.print("[dim]Press Enter without keys to skip a category.[/dim]")
        self.console.print()
        
        try:
            if not questionary.confirm("Continue with bulk assignment?").ask():
                return
        except Exception:
            try:
                response = input("Continue with bulk assignment? [y/n]: ").lower().strip()
                if response not in ['y', 'yes']:
                    return
            except:
                return
        
        total_categories = len(categories)
        
        for i, (name, config) in enumerate(categories.items(), 1):
            # Clear screen and show progress
            self.console.print(f"\n{'='*60}")
            self.console.print(f"[bold cyan]Category {i}/{total_categories}: {name}[/bold cyan]")
            self.console.print(f"[dim]Sounds: {config.sound_count}[/dim]")
            self.console.print('='*60)
            
            # Show current shortcut
            self._show_current_shortcut(config)
            
            # Offer to skip this category
            if config.keyboard_shortcut:
                try:
                    if not questionary.confirm(f"Change shortcut for '{name}'?").ask():
                        self.console.print(f"[yellow]Skipped '{name}' - keeping current shortcut[/yellow]")
                        continue
                except Exception:
                    try:
                        response = input(f"Change shortcut for '{name}'? [y/n]: ").lower().strip()
                        if response not in ['y', 'yes']:
                            self.console.print(f"[yellow]Skipped '{name}' - keeping current shortcut[/yellow]")
                            continue
                    except:
                        self.console.print(f"[yellow]Skipped '{name}' - input error[/yellow]")
                        continue
            
            # Capture new shortcut
            new_shortcut = self.capture_keyboard_shortcut(f"shortcut for '{name}' ({i}/{total_categories})")
            
            if new_shortcut:
                # Check for conflicts and save
                if self._check_shortcut_conflicts(name, new_shortcut):
                    self._save_category_shortcut(name, new_shortcut)
                    self.console.print(f"[green]Assigned shortcut to '{name}'[/green]")
                else:
                    self.console.print(f"[yellow]Skipped '{name}' due to conflict[/yellow]")
            else:
                self.console.print(f"[yellow]Skipped '{name}' - no shortcut assigned[/yellow]")
            
            # Small pause before next category (except for last one)
            if i < total_categories:
                self.console.print(f"\n[dim]Moving to next category...[/dim]")
                time.sleep(1)
        
        self.console.print(f"\n[bold green]Bulk assignment complete![/bold green]")
        self.console.print(f"[dim]Processed {total_categories} categories[/dim]")
    
    def _show_current_shortcut(self, category_config: CategoryConfig) -> None:
        """Display current shortcut for category."""
        if category_config.keyboard_shortcut:
            current = key_combination_to_string(category_config.keyboard_shortcut)
            self.console.print(f"[dim]Current shortcut: {current}[/dim]")
        else:
            self.console.print("[dim]No shortcut currently assigned[/dim]")
    
    def _check_shortcut_conflicts(self, selected_category: str, new_shortcut: List[str]) -> bool:
        """Check for shortcut conflicts and ask user to proceed if conflicts exist."""
        shortcut_key = tuple(sorted(new_shortcut))
        
        # Get all current shortcuts excluding this category
        all_categories = self.config_manager.get_all_categories()
        existing_shortcuts = {}
        
        for name, config in all_categories.items():
            if name != selected_category and config.keyboard_shortcut:
                existing_key = tuple(sorted(config.keyboard_shortcut))
                existing_shortcuts[existing_key] = name
        
        # Check stop shortcut
        stop_shortcut = self.config_manager.get_stop_shortcut()
        if stop_shortcut:
            stop_key = tuple(sorted(stop_shortcut))
            existing_shortcuts[stop_key] = "stop_playback"
        
        if shortcut_key in existing_shortcuts:
            conflicting_item = existing_shortcuts[shortcut_key]
            combo_str = key_combination_to_string(new_shortcut)
            
            self.console.print(f"[red]Warning: Conflict detected![/red]")
            self.console.print(f"[red]Shortcut '{combo_str}' is already used by: {conflicting_item}[/red]")
            
            try:
                return Confirm.ask("Assign anyway?")
            except Exception:
                # Fallback for terminal compatibility issues
                try:
                    response = input("Assign anyway? [y/n]: ").lower().strip()
                    return response in ['y', 'yes']
                except:
                    return False
        
        return True
    
    def _save_category_shortcut(self, selected_category: str, new_shortcut: List[str]) -> None:
        """Save category shortcut to configuration."""
        success = self.config_manager.update_category_shortcut(selected_category, new_shortcut)
        if success:
            self.config_manager.save_config()
            combo_str = key_combination_to_string(new_shortcut)
            self.console.print(f"[green]Assigned '{combo_str}' to '{selected_category}'[/green]")
        else:
            self.console.print("[red]✗ Failed to save shortcut[/red]")
    
    def set_stop_shortcut(self) -> None:
        """Set the pause/resume toggle shortcut."""
        try:
            self.console.print("\n[bold]⏯️ Set Pause/Resume Shortcut[/bold]")
            
            if not self.config_manager:
                self.console.print("[red]✗ Configuration not initialized[/red]")
                return
            
            current = self.config_manager.get_stop_shortcut()
            if current:
                combo_str = key_combination_to_string(current)
                self.console.print(f"[dim]Current pause/resume shortcut: {combo_str}[/dim]")
            else:
                self.console.print("[dim]No pause/resume shortcut currently set[/dim]")
            
            new_shortcut = self.capture_keyboard_shortcut("pause/resume toggle shortcut")
            if not new_shortcut:
                return
            
            # Check for conflicts (temporarily set to check)
            old_shortcut = current
            self.config_manager.set_stop_shortcut(new_shortcut)
            conflicts = self.config_manager.get_conflicting_shortcuts()
            self.config_manager.set_stop_shortcut(old_shortcut or [])
            
            shortcut_key = tuple(sorted(new_shortcut))
            if shortcut_key in conflicts:
                conflicting_items = conflicts[shortcut_key]
                combo_str = key_combination_to_string(new_shortcut)
                items_str = ", ".join([item for item in conflicting_items if item != "stop_playback"])
                
                if items_str:
                    self.console.print(f"[red]Warning: Conflict detected![/red]")
                    self.console.print(f"[red]Shortcut '{combo_str}' is already used by: {items_str}[/red]")
                    
                    try:
                        if not Confirm.ask("Assign anyway?"):
                            return
                    except KeyboardInterrupt:
                        self.console.print("\n[yellow]Operation cancelled[/yellow]")
                        return
                    except Exception as e:
                        self.console.print(f"\n[yellow]Confirmation cancelled: {e}[/yellow]")
                        return
            
            # Save shortcut
            self.config_manager.set_stop_shortcut(new_shortcut)
            self.config_manager.save_config()
            
            combo_str = key_combination_to_string(new_shortcut)
            self.console.print(f"[green]Set pause/resume shortcut to '{combo_str}'[/green]")
            
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Operation cancelled by user[/yellow]")
        except Exception as e:
            self.console.print(f"\n[red]Unexpected error in set_stop_shortcut: {e}[/red]")
            import traceback
            self.console.print(f"[dim]Debug: {traceback.format_exc()}[/dim]")
            try:
                input("\nPress Enter to continue...")
            except (KeyboardInterrupt, EOFError):
                pass
    
    def test_shortcuts(self) -> None:
        """Test keyboard shortcuts with Soundpad."""
        self.console.print("\n[bold]Test Shortcuts[/bold]")
        
        if not self.config_manager:
            self.console.print("[red]✗ Configuration not initialized[/red]")
            return
        
        if not self.soundpad_client or not self.soundpad_client.is_alive():
            self.console.print("[red]✗ Not connected to Soundpad[/red]")
            return
        
        categories = self.config_manager.get_enabled_categories()
        if not categories:
            self.console.print("[dim]No enabled categories with shortcuts to test[/dim]")
            return
        
        # Select category to test
        test_choices = []
        for name, config in categories.items():
            if config.keyboard_shortcut:
                shortcut_str = key_combination_to_string(config.keyboard_shortcut)
                test_choices.append(questionary.Choice(f"{name} - {shortcut_str}", value=name))
        
        if not test_choices:
            self.console.print("[dim]No categories have shortcuts assigned[/dim]")
            return
        
        test_choices.append(questionary.Choice("Test pause/resume shortcut", value="__stop__"))
        
        try:
            selected = questionary.select(
                "Select shortcut to test:",
                choices=test_choices,
                style=self.style
            ).ask()
        except Exception:
            # Fallback for terminal compatibility issues
            self.console.print("[dim]Available shortcuts to test:[/dim]")
            option_map = {}
            for i, choice in enumerate(test_choices, 1):
                option_map[str(i)] = choice.value
                self.console.print(f"  {i}. {choice.title}")
            
            while True:
                try:
                    choice_input = input("\nSelect test option (number or 'q' to go back): ").strip()
                    if choice_input.lower() == 'q':
                        return
                    if choice_input in option_map:
                        selected = option_map[choice_input]
                        break
                    self.console.print("[red]Invalid choice. Try again.[/red]")
                except KeyboardInterrupt:
                    return
                except:
                    return
        
        if not selected:
            return
        
        # Test the selected shortcut
        if selected == "__stop__":
            self.console.print("[cyan]Testing pause/resume shortcut...[/cyan]")
            success = self.soundpad_client.toggle_pause()
            if success:
                self.console.print("[green]Pause/resume toggle sent successfully[/green]")
            else:
                self.console.print("[red]✗ Pause/resume toggle failed[/red]")
        else:
            category_config = categories[selected]
            self.console.print(f"[cyan]Testing category '{selected}'...[/cyan]")
            
            # Play random sound from category
            success = self.soundpad_client.play_random_sound_from_category(
                category_config.soundpad_category_id,
                speakers=True,
                microphone=True
            )
            
            if success:
                self.console.print(f"[green]Played random sound from '{selected}'[/green]")
            else:
                self.console.print(f"[red]✗ Failed to play sound from '{selected}'[/red]")
    
    def reset_all_shortcuts(self) -> None:
        """Reset all keyboard shortcuts."""
        self.console.print("\n[bold]🔄 Reset Shortcuts[/bold]")
        
        if not self.config_manager:
            self.console.print("[red]✗ Configuration not initialized[/red]")
            return
        
        categories = self.config_manager.get_all_categories()
        shortcut_count = sum(1 for config in categories.values() if config.keyboard_shortcut)
        stop_shortcut = self.config_manager.get_stop_shortcut()
        
        if stop_shortcut:
            shortcut_count += 1
        
        if shortcut_count == 0:
            self.console.print("[dim]No shortcuts to reset[/dim]")
            return
        
        self.console.print(f"[yellow]This will remove {shortcut_count} shortcuts[/yellow]")
        
        try:
            if not Confirm.ask("Are you sure you want to reset all shortcuts?"):
                return
        except Exception:
            try:
                response = input("Are you sure you want to reset all shortcuts? [y/n]: ").lower().strip()
                if response not in ['y', 'yes']:
                    return
            except:
                return
        
        # Reset all shortcuts
        for name in categories.keys():
            self.config_manager.update_category_shortcut(name, [])
        
        self.config_manager.set_stop_shortcut([])
        self.config_manager.save_config()
        
        self.console.print("[green]All shortcuts have been reset[/green]")
    
    def main_menu(self) -> None:
        """Display and handle main menu."""
        while True:
            self.console.print()
            
            choices = [
                questionary.Choice("⌨️ View current shortcuts", value="view"),
                questionary.Choice("🎯 Assign category shortcuts", value="assign"),
                questionary.Choice("⏯️ Set pause/resume shortcut", value="stop"),
                questionary.Choice("🧪 Test shortcuts", value="test"),
                questionary.Choice("🔄 Reset all shortcuts", value="reset"),
                questionary.Choice("❌ Exit", value="exit")
            ]
            
            try:
                choice = questionary.select(
                    "What would you like to do?",
                    choices=choices,
                    style=self.style
                ).ask()
                
                if not choice or choice == "exit":
                    break
                
                if choice == "view":
                    self.view_current_shortcuts()
                
                elif choice == "assign":
                    self.assign_category_shortcuts()
                
                elif choice == "stop":
                    self.set_stop_shortcut()
                
                elif choice == "test":
                    self.test_shortcuts()
                
                elif choice == "reset":
                    self.reset_all_shortcuts()
                    
            except KeyboardInterrupt:
                self.console.print("\n[yellow]Operation cancelled by user[/yellow]")
                break
            except Exception as e:
                error_msg = str(e)
                if "Found xterm" in error_msg or "Windows console" in error_msg:
                    self.console.print(f"\n[yellow]Terminal compatibility issue detected.[/yellow]")
                    self.console.print(f"[dim]Try running this in cmd.exe or Windows Terminal for better compatibility.[/dim]")
                    self.console.print(f"[dim]Error: {error_msg}[/dim]")
                else:
                    self.console.print(f"\n[red]Menu error: {e}[/red]")
                
                try:
                    response = input("Continue anyway? [y/n]: ").lower().strip()
                    if response not in ['y', 'yes']:
                        break
                except:
                    self.console.print("[yellow]Exiting due to error[/yellow]")
                    break
            
            # Pause before returning to menu only for actions that need it
            # Don't pause for view, navigation actions, or if we're exiting
            if choice and choice not in ["view", "exit"] and choice != "__go_back__":
                try:
                    input("\nPress Enter to continue...")
                except KeyboardInterrupt:
                    break
                except:
                    pass  # Ignore input errors
    
    def run(self) -> None:
        """Run the configuration tool."""
        self.print_header()
        
        # Initialize components
        if not self.init_config():
            try:
                input("\nPress Enter to exit...")
            except (KeyboardInterrupt, EOFError):
                pass
            return
        
        # Check if categories exist
        categories = self.config_manager.get_all_categories()
        if not categories:
            self.console.print("[yellow]Warning: No categories configured yet.[/yellow]")
            self.console.print("[dim]Run Soundpad-setup.py first to import sound categories.[/dim]")
            try:
                if not Confirm.ask("Continue anyway?"):
                    return
            except Exception:
                try:
                    response = input("Continue anyway? [y/n]: ").lower().strip()
                    if response not in ['y', 'yes']:
                        return
                except:
                    return
        
        # Try to connect to Soundpad
        self.connect_to_soundpad()
        
        # Show main menu
        try:
            self.main_menu()
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Configuration interrupted by user[/yellow]")
        except Exception as e:
            self.console.print(f"\n[red]Unexpected error: {e}[/red]")
            try:
                input("\nPress Enter to continue...")
            except (KeyboardInterrupt, EOFError):
                pass
        
        self.console.print("\n[green]Configuration complete! Run Soundpad-run.py to start using shortcuts.[/green]")
        try:
            input("\nPress Enter to exit...")
        except (KeyboardInterrupt, EOFError):
            pass  # Allow graceful exit
    
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
            self.console.print(f"[red]✗ Soundpad executable not found: {soundpad_path}[/red]")
            return False
        
        # Launch Soundpad using PowerShell (reliable Windows method)
        try:
            self.console.print("[cyan]🚀 Launching Soundpad...[/cyan]")
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
                        self.console.print("[green]Soundpad launched successfully[/green]")
                        return True
                except:
                    pass
            
            self.console.print("[yellow]Warning: Soundpad launched but not responding yet. Please wait a moment and try again.[/yellow]")
            return False
            
        except Exception as e:
            self.console.print(f"[red]✗ Failed to launch Soundpad: {e}[/red]")
            try:
                input("\nPress Enter to continue...")
            except (KeyboardInterrupt, EOFError):
                pass
            return False
    


if __name__ == "__main__":
    config_tool = SoundpadConfig()
    config_tool.run()
#!/usr/bin/env python3
"""
Soundpad Commander Setup Tool

Interactive CLI tool for setting up sound categories and importing
audio files into Soundpad from organized folder structures.
"""

import sys
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add current directory to path for imports (scripts now in root)
sys.path.insert(0, os.path.dirname(__file__))

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
    from rich.prompt import Prompt, Confirm
    from rich.layout import Layout
    from rich.align import Align
    from rich.text import Text
    import questionary
    from questionary import Style
except ImportError as e:
    print(f"Error: Required packages not installed. Run: pip install -r requirements.txt")
    print(f"Missing: {e}")
    sys.exit(1)

try:
    from Soundpad.soundpad_client import SoundpadClient, create_client
    from Soundpad.file_scanner import FileScanner, scan_for_soundpad_categories, CategoryInfo
    from Soundpad.config_manager import ConfigManager, create_default_config
except ImportError as e:
    print(f"Error: Could not import Soundpad modules: {e}")
    print("Make sure you're running from the correct directory.")
    sys.exit(1)


class SoundpadSetup:
    """Main setup tool for Soundpad Commander."""
    
    def __init__(self):
        """Initialize the setup tool."""
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
                Text("SOUNDPAD COMMANDER\nSETUP TOOL", style="bold blue"),
                vertical="middle"
            ),
            style="blue",
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
                self.console.print(f"[green]✓ Connected to Soundpad {version}[/green]")
                return True
            else:
                self.console.print("[yellow]⚠ Soundpad is not running[/yellow]")
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
    
    def scan_for_folders(self) -> Optional[Dict[str, CategoryInfo]]:
        """Scan for sound folders interactively."""
        self.console.print("\n[bold]📁 Scan for Sound Folders[/bold]")
        
        # Get directory to scan
        directory = questionary.path(
            "Enter folder path to scan:"
        ).ask()
        
        if not directory:
            return None
        
        directory = os.path.abspath(directory)
        
        if not os.path.exists(directory):
            self.console.print(f"[red]✗ Directory not found: {directory}[/red]")
            return None
        
        # Scanning options
        self.console.print(f"\n[dim]Scanning: {directory}[/dim]")
        
        # Use minimum files per category as 1 (hardcoded)
        min_files = 1
        
        # Perform scan with progress indicator
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
            console=self.console
        ) as progress:
            task = progress.add_task("Scanning directories...", total=None)
            
            try:
                scanner = FileScanner()
                categories = scanner.scan_directory(directory)
                categories = scanner.filter_categories_by_size(categories, min_files=min_files)
                
                progress.update(task, description="Scan complete!")
                time.sleep(0.5)
                
            except Exception as e:
                self.console.print(f"[red]✗ Scanning failed: {e}[/red]")
                return None
        
        # Display results
        if not categories:
            self.console.print("[yellow]No suitable folders found.[/yellow]")
            self.console.print(f"[dim]Requirements: Folders with at least {min_files} audio file(s)[/dim]")
            return None
        
        # Show scan results table
        self.display_scan_results(categories)
        
        return categories
    
    def display_scan_results(self, categories: Dict[str, CategoryInfo]) -> None:
        """Display scan results in a table."""
        table = Table(title="🔍 Discovered Categories", show_header=True, header_style="bold blue")
        table.add_column("Category", style="cyan", no_wrap=True)
        table.add_column("Files", justify="center")
        table.add_column("Size (MB)", justify="right")
        table.add_column("Path", style="dim")
        
        total_files = 0
        total_size = 0
        
        for name, category in categories.items():
            table.add_row(
                name,
                str(category.total_files),
                f"{category.size_mb:.1f}",
                str(Path(category.path).name)  # Show only folder name
            )
            total_files += category.total_files
            total_size += category.total_size
        
        table.add_section()
        table.add_row(
            "[bold]TOTAL[/bold]",
            f"[bold]{total_files}[/bold]",
            f"[bold]{total_size / (1024*1024):.1f}[/bold]",
            f"[dim]{len(categories)} categories[/dim]"
        )
        
        self.console.print("\n")
        self.console.print(table)
        self.console.print()
    
    def import_to_soundpad(self, categories: Dict[str, CategoryInfo]) -> bool:
        """Import categories and files to Soundpad."""
        if not self.soundpad_client:
            self.console.print("[red]✗ Not connected to Soundpad[/red]")
            return False
        
        self.console.print("\n[bold]📥 Import to Soundpad[/bold]")
        
        # Import with progress tracking
        total_files = sum(cat.total_files for cat in categories.values())
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=self.console
        ) as progress:
            
            main_task = progress.add_task("Importing categories...", total=len(categories))
            file_task = progress.add_task("Processing files...", total=total_files)
            
            imported_categories = {}
            processed_files = 0
            
            for cat_name, category in categories.items():
                # Check if Soundpad is still alive before processing
                if not self.soundpad_client.is_alive():
                    self.console.print(f"[red]✗ Soundpad connection lost. Stopping import.[/red]")
                    break
                progress.update(main_task, description=f"Creating category: {cat_name}")
                
                # Add category to Soundpad
                success = self.soundpad_client.add_category(cat_name)
                if not success:
                    self.console.print(f"[red]✗ Failed to create category: {cat_name}[/red]")
                    continue
                
                # Longer delay to allow Soundpad to process the category creation
                time.sleep(0.5)
                
                # Try multiple times to get category ID with backoff
                category_id = None
                for attempt in range(3):
                    category_id = self._get_category_id_from_soundpad(cat_name)
                    if category_id is not None:
                        break
                    time.sleep(0.5 * (attempt + 1))  # Progressive backoff
                
                if category_id is None:
                    self.console.print(f"[red]✗ Failed to get category ID for: {cat_name}[/red]")
                    continue
                
                # Add sounds to category with error handling
                for audio_file in category.audio_files:
                    progress.update(file_task, description=f"Adding: {audio_file.name}")
                    
                    try:
                        success = self.soundpad_client.add_sound(
                            audio_file.path, category_id, -1
                        )
                        
                        if success:
                            processed_files += 1
                        else:
                            self.console.print(f"[yellow]⚠ Failed to add: {audio_file.name}[/yellow]")
                    
                    except Exception as e:
                        self.console.print(f"[yellow]⚠ Error adding {audio_file.name}: {e}[/yellow]")
                    
                    progress.update(file_task, advance=1)
                    time.sleep(0.05)  # Increased delay to prevent Soundpad crashes
                
                # Save category info for config
                imported_categories[cat_name] = {
                    'category_id': category_id,
                    'folder_path': category.path,
                    'sound_count': category.total_files
                }
                
                progress.update(main_task, advance=1)
        
        # Update configuration
        if imported_categories:
            self.update_config_with_categories(imported_categories)
            
            self.console.print(f"\n[green]✓ Successfully imported {len(imported_categories)} categories[/green]")
            self.console.print(f"[green]✓ Processed {processed_files}/{total_files} audio files[/green]")
            
            # Show warning if not all files were processed
            if processed_files < total_files:
                missed_files = total_files - processed_files
                self.console.print(f"[yellow]⚠ {missed_files} files were not imported. This may be due to:[/yellow]")
                self.console.print("  [dim]• Soundpad connection issues[/dim]")
                self.console.print("  [dim]• File format not supported[/dim]")
                self.console.print("  [dim]• File access permissions[/dim]")
                self.console.print("  [dim]• Soundpad being overwhelmed with requests[/dim]")
                self.console.print("  [yellow]💡 Try running the import again or reduce the import speed[/yellow]")
            
            return True
        else:
            self.console.print(f"[red]✗ Failed to import categories[/red]")
            return False
    
    def _get_category_id_from_soundpad(self, category_name: str) -> Optional[int]:
        """
        Get the actual category ID from Soundpad after creating a category.
        
        Args:
            category_name: Name of the category to find
            
        Returns:
            Category ID from Soundpad or None if not found
        """
        if not self.soundpad_client:
            return None
        
        try:
            # Get categories from Soundpad with retry mechanism
            categories_xml = None
            for attempt in range(3):
                categories_xml = self.soundpad_client.get_categories(with_sounds=False, with_icons=False)
                if categories_xml:
                    break
                time.sleep(0.2)
            
            if not categories_xml:
                return None
            
            # Parse XML to find category ID by name - improved robustness
            import re
            import xml.etree.ElementTree as ET
            
            # Clean the category name for matching
            clean_category_name = category_name.strip()
            
            # First try proper XML parsing
            try:
                root = ET.fromstring(categories_xml)
                for category in root.iter('category'):
                    name_attr = category.get('name', '').strip()
                    index_attr = category.get('index', '')
                    
                    # Try exact match first, then case insensitive
                    if (name_attr == clean_category_name or 
                        name_attr.lower() == clean_category_name.lower()) and index_attr.isdigit():
                        return int(index_attr)
            except ET.ParseError:
                # Fall back to regex parsing if XML is malformed
                pass
            
            # Enhanced regex patterns with better escaping
            escaped_name = re.escape(clean_category_name)
            patterns = [
                # Exact match patterns
                rf'<category[^>]*index="(\d+)"[^>]*name="{escaped_name}"[^>]*>',
                rf'<category[^>]*name="{escaped_name}"[^>]*index="(\d+)"[^>]*>',
                # Case insensitive patterns
                rf'<category[^>]*index="(\d+)"[^>]*name="{escaped_name}"[^>]*>',
                rf'<category[^>]*name="{escaped_name}"[^>]*index="(\d+)"[^>]*>',
            ]
            
            for pattern in patterns:
                try:
                    match = re.search(pattern, categories_xml, re.IGNORECASE)
                    if match and match.group(1).isdigit():
                        return int(match.group(1))
                except (AttributeError, ValueError):
                    continue
            
            # Final fallback: extract all category pairs and match with fuzzy matching
            try:
                # More comprehensive regex to catch various XML formats
                category_patterns = [
                    r'<category[^>]*index="(\d+)"[^>]*name="([^"]*)"[^>]*>',
                    r'<category[^>]*name="([^"]*)"[^>]*index="(\d+)"[^>]*>',
                ]
                
                for pattern in category_patterns:
                    matches = re.findall(pattern, categories_xml, re.IGNORECASE)
                    for match in matches:
                        if len(match) == 2:
                            if pattern.find('index') < pattern.find('name'):
                                cat_id, cat_name = match
                            else:
                                cat_name, cat_id = match
                            
                            if (cat_id.isdigit() and 
                                (cat_name.strip() == clean_category_name or
                                 cat_name.strip().lower() == clean_category_name.lower())):
                                return int(cat_id)
            except (ValueError, AttributeError):
                pass
            
            return None
            
        except Exception as e:
            self.console.print(f"[yellow]⚠ Error getting category ID for '{category_name}': {e}[/yellow]")
            return None
    
    def update_config_with_categories(self, categories: Dict[str, dict]) -> None:
        """Update configuration with imported categories."""
        if not self.config_manager:
            return
        
        for cat_name, cat_info in categories.items():
            self.config_manager.add_category(
                name=cat_name,
                soundpad_id=cat_info['category_id'],
                folder_path=cat_info['folder_path']
            )
            self.config_manager.update_category_sound_count(
                cat_name, cat_info['sound_count']
            )
        
        self.config_manager.save_config()
    
    def view_current_categories(self) -> None:
        """Display current Soundpad categories."""
        self.console.print("\n[bold]📋 Current Categories[/bold]")
        
        if not self.config_manager:
            self.console.print("[red]✗ Configuration not initialized[/red]")
            return
        
        categories = self.config_manager.get_all_categories()
        
        if not categories:
            self.console.print("[dim]No categories configured yet.[/dim]")
            return
        
        table = Table(show_header=True, header_style="bold blue")
        table.add_column("Category", style="cyan")
        table.add_column("ID", justify="center")
        table.add_column("Sounds", justify="center")
        table.add_column("Shortcut", justify="center")
        table.add_column("Status")
        table.add_column("Folder Path", style="dim")
        
        for name, config in categories.items():
            shortcut = "+".join(config.keyboard_shortcut) if config.keyboard_shortcut else "[dim]None[/dim]"
            status = "[green]✓ Enabled[/green]" if config.enabled else "[red]✗ Disabled[/red]"
            
            table.add_row(
                name,
                str(config.soundpad_category_id),
                str(config.sound_count),
                shortcut,
                status,
                config.folder_path
            )
        
        self.console.print(table)
        self.console.print()
    
    def remove_old_categories(self) -> None:
        """Remove old categories interactively."""
        self.console.print("\n[bold]🗑️ Remove Categories[/bold]")
        
        if not self.config_manager:
            self.console.print("[red]✗ Configuration not initialized[/red]")
            return
        
        categories = self.config_manager.get_all_categories()
        if not categories:
            self.console.print("[dim]No categories to remove.[/dim]")
            return
        
        # Select categories to remove
        category_choices = [
            questionary.Choice(f"{name} ({config.sound_count} sounds)", value=name)
            for name, config in categories.items()
        ]
        category_choices.append(questionary.Choice("← Go back", value="__back__"))
        
        selected = questionary.checkbox(
            "Select categories to remove:",
            choices=category_choices
        ).ask()
        
        if not selected or "__back__" in selected:
            return
        
        # Confirm removal
        if not Confirm.ask(f"Remove {len(selected)} categories?"):
            return
        
        # Remove from Soundpad and config
        removed_count = 0
        for cat_name in selected:
            config = categories[cat_name]
            
            # Remove from Soundpad if connected
            if self.soundpad_client and self.soundpad_client.is_alive():
                success = self.soundpad_client.remove_category(config.soundpad_category_id)
                if not success:
                    self.console.print(f"[yellow]⚠ Could not remove category from Soundpad: {cat_name}[/yellow]")
            
            # Remove from config
            if self.config_manager.remove_category(cat_name):
                removed_count += 1
        
        if removed_count > 0:
            self.config_manager.save_config()
            self.console.print(f"[green]✓ Removed {removed_count} categories[/green]")
        else:
            self.console.print("[red]✗ No categories were removed[/red]")
    
    def configure_soundpad_path(self) -> None:
        """Configure Soundpad executable path."""
        self.console.print("\n[bold]⚙️ Configure Soundpad Path[/bold]")
        
        if not self.config_manager:
            self.console.print("[red]✗ Configuration not initialized[/red]")
            return
        
        current_path = self.config_manager.get_soundpad_executable_path()
        self.console.print(f"[dim]Current path: {current_path}[/dim]")
        
        new_path = questionary.path(
            "Enter Soundpad.exe path:",
            default=current_path
        ).ask()
        
        if not new_path or new_path == current_path:
            return
        
        if not os.path.exists(new_path):
            if not Confirm.ask("Path does not exist. Save anyway?"):
                return
        
        self.config_manager.set_soundpad_executable_path(new_path)
        
        # Ask about auto-launch
        auto_launch = Confirm.ask("Auto-launch Soundpad when needed?")
        self.config_manager.set_auto_launch_soundpad(auto_launch)
        
        self.config_manager.save_config()
        self.console.print("[green]✓ Soundpad path configured[/green]")
    
    def main_menu(self) -> None:
        """Display and handle main menu."""
        while True:
            self.console.print()
            
            choices = [
                questionary.Choice("🔍 Scan for sound folders", value="scan"),
                questionary.Choice("📋 View current categories", value="view"),
                questionary.Choice("🗑️ Remove old categories", value="remove"),
                questionary.Choice("⚙️ Configure Soundpad path", value="config"),
                questionary.Choice("❌ Exit", value="exit")
            ]
            
            choice = questionary.select(
                "What would you like to do?",
                choices=choices
            ).ask()
            
            if choice == "scan":
                categories = self.scan_for_folders()
                if categories and Confirm.ask("📥 Import to Soundpad\nImport these categories to Soundpad?"):
                    self.import_to_soundpad(categories)
            
            elif choice == "view":
                self.view_current_categories()
            
            elif choice == "remove":
                self.remove_old_categories()
            
            elif choice == "config":
                self.configure_soundpad_path()
            
            elif choice == "exit":
                break
            
            # Pause before returning to menu
            input("\nPress Enter to continue...")
    
    def run(self) -> None:
        """Run the setup tool."""
        self.print_header()
        
        # Initialize components
        if not self.init_config():
            input("\nPress Enter to exit...")
            return
        
        # Check first run
        if self.config_manager.is_first_run():
            self.console.print("[yellow]👋 Welcome! This appears to be your first time running Soundpad Commander.[/yellow]")
            self.console.print("[dim]Let's configure your Soundpad path first...[/dim]")
            
            # Configure Soundpad path on first run
            self.console.print("\n[bold]⚙️ Configure Soundpad Path[/bold]")
            current_path = self.config_manager.get_soundpad_executable_path()
            self.console.print(f"Current path: {current_path}")
            
            new_path = questionary.path(
                "Enter Soundpad.exe path:",
                default=current_path
            ).ask()
            
            if new_path and new_path != current_path:
                if not os.path.exists(new_path):
                    if not Confirm.ask("Path does not exist. Save anyway?"):
                        new_path = current_path
                
                if new_path != current_path:
                    self.config_manager.set_soundpad_executable_path(new_path)
                    
                    # Ask about auto-launch
                    auto_launch = Confirm.ask("Auto-launch Soundpad when needed?")
                    self.config_manager.set_auto_launch_soundpad(auto_launch)
                    
                    self.config_manager.save_config()
                    self.console.print("[green]✓ Soundpad path configured[/green]")
            
            self.console.print("\n[dim]Now let's set up your sound categories...[/dim]")
        
        # Try to connect to Soundpad
        self.connect_to_soundpad()
        
        # Show main menu
        try:
            self.main_menu()
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Setup interrupted by user[/yellow]")
        except Exception as e:
            self.console.print(f"\n[red]Unexpected error: {e}[/red]")
            input("\nPress Enter to continue...")
        
        self.console.print("\n[green]Setup complete! Run Soundpad-config.py to set up keyboard shortcuts.[/green]")
        input("\nPress Enter to exit...")
    
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
                        self.console.print("[green]✓ Soundpad launched successfully[/green]")
                        return True
                except:
                    pass
            
            self.console.print("[yellow]⚠ Soundpad launched but not responding yet. Please wait a moment and try again.[/yellow]")
            return False
            
        except Exception as e:
            self.console.print(f"[red]✗ Failed to launch Soundpad: {e}[/red]")
            input("\nPress Enter to continue...")
            return False
    


if __name__ == "__main__":
    setup = SoundpadSetup()
    setup.run()
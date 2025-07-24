# Soundpad Commander

**Soundpad Commander** Bringing organized sound effects to your fingertips! 🎵⌨️
it's a Windows CLI application that integrates with Soundpad to play random sound effects from organized folders using customizable global keyboard shortcuts.

![Soundpad Commander](https://img.shields.io/badge/Platform-Windows-blue) ![Python](https://img.shields.io/badge/Python-3.8%2B-green) ![License](https://img.shields.io/badge/License-MIT-yellow)

What's Soundpad? it's a Windows tool that lets you play custom sounds through your microphone in voice chats or games, acting like a soundboard.

## Features

- 🎵 **Random Sound Playback** - Play random sounds from organized categories
- ⌨️ **Global Keyboard Shortcuts** - Works in games, fullscreen apps, any Windows context (uses keyboard library for reliability)
- ⏯️ **Pause/Resume Toggle** - Same shortcut pauses and resumes audio instead of stopping completely
- 📁 **Automatic Folder Import** - Scan directories and import sounds into Soundpad categories
- 🎮 **Interactive CLI** - Beautiful Rich-based interfaces for setup and configuration
- ⚙️ **YAML Configuration** - Human-readable configuration files
- 🔄 **Real-time Key Capture** - Live keyboard shortcut assignment during setup
- 📊 **Live Status Display** - Real-time monitoring of shortcuts and activity
- 🚀 **Auto-launch Soundpad** - Automatically starts Soundpad when needed
- 🛡️ **Automatic Admin Elevation** - Requests administrator privileges for global shortcuts automatically

## Architecture

### Core Components

1. **Soundpad Setup Tool** (`1- Soundpad-setup.py`) - One-time folder import and category setup
2. **Soundpad Config Tool** (`2- Soundpad-config.py`) - Manage keyboard shortcuts and folder mappings  
3. **Soundpad Commander** (`3- Soundpad-run.py`) - Main application with global keyboard listener

### Technology Stack

- **Language**: Python 3.8+ (Cross-platform, excellent Windows support)
- **Config Format**: YAML (Human-readable, easy to edit)
- **CLI Interface**: Rich interactive menus
- **Dependencies**:
  - `rich>=13.0.0` - Beautiful CLI interfaces with menus, tables, progress bars
  - `questionary>=1.10.0` - Interactive prompts and selections
  - `pynput>=1.7.6` - Interactive key capture during configuration
  - `keyboard>=0.13.5` - Global keyboard shortcuts (more reliable than pynput on Windows)
  - `PyYAML>=6.0` - YAML configuration management

## Installation

1. **Prerequisites**:
   - Windows 10/11
   - Python 3.8 or higher
   - Soundpad (full version)

2. **Clone or Download**:
   ```bash
   cd Soundpad-commander
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```


## Quick Start

### Step 1: Setup Sound Categories

Run the setup tool "1- Soundpad-setup.py" to scan for sound folders and import them into Soundpad:

**Setup Process:**
1. Select "Scan for sound folders"
2. Enter the path to your sound effects directory (e.g., `C:\SoundEffects`)
3. Review discovered categories
4. Confirm import to Soundpad

**Folder Structure Example:**
```
C:\SoundEffects\
├── explosions\
│   ├── explosion1.mp3
│   ├── explosion2.wav
│   └── explosion3.ogg
├── gunshots\
│   ├── rifle1.mp3
│   └── pistol2.wav
└── ambient\
    ├── forest.mp3
    └── rain.wav
```

### Step 2: Configure Keyboard Shortcuts

Run the config tool "2- Soundpad-config.py" to assign keyboard shortcuts to categories:

**Configuration Process:**
1. Select "Assign category shortcuts"
2. Choose a category to configure
3. Press your desired key combination (e.g., `Alt+1`)
4. Press Enter to confirm
5. Repeat for other categories and set stop shortcut

### Step 3: Run Soundpad Commander

Start the main application "3- Soundpad-run.py" to begin using keyboard shortcuts:

**Runtime Features:**
- Interactive status display showing connection status, shortcuts, and activity
- Global keyboard shortcut detection
- Automatic Soundpad connection monitoring
- Real-time activity logging

## Usage Examples

### Keyboard Shortcuts
- Press `Alt+1` → Random sound from "explosions" category plays
- Press `Alt+2` → Random sound from "ambient" category plays  
- Press `Alt+0` → **Pause/Resume** currently playing sound (toggles between pause and resume)

## Configuration File

The configuration is stored in `Soundpad-config.yaml`:

```yaml
soundpad:
  executable_path: "C:\\Program Files\\Soundpad\\Soundpad.exe"
  pipe_path: "\\\\.\\pipe\\sp_remote_control"
  auto_launch: true

shortcuts:
  stop_playback: ["alt", "0"]  # Actually performs pause/resume toggle

categories:
  explosions:
    soundpad_category_id: 1
    keyboard_shortcut: ["alt", "1"]
    folder_path: "C:\\SoundEffects\\explosions"
    enabled: true
    sound_count: 15

settings:
  play_on_speakers: true
  play_on_microphone: true
  log_level: "INFO"
  show_notifications: true
```

See `Soundpad-config-template.yaml` for detailed configuration options.

## Supported Audio Formats

- **Audio Files**: `.mp3`, `.wav`, `.ogg`, `.m4a`, `.aac`, `.flac`, `.wma`
- **Video Files**: `.mp4`, `.avi`, `.mov`, `.mkv`, `.webm` (audio track only)

## Keyboard Shortcuts

### Key Names
- **Modifiers**: `ctrl`, `alt`, `shift`, `cmd` (Windows key)
- **Function Keys**: `f1`, `f2`, `f3`, ... `f12`
- **Regular Keys**: `a-z`, `0-9`
- **Special Keys**: `space`, `enter`, `tab`, `esc`, `backspace`, `delete`, etc.

### Multi-Key Combinations
Supports complex combinations like:
- `["ctrl", "alt", "f1"]`
- `["shift", "ctrl", "s"]`
- `["alt", "1"]`

## Troubleshooting

### Common Issues

**"Cannot connect to Soundpad"**
- Verify Soundpad path in configuration
- Ensure Soundpad is running (otherwise the tool will try to run it automatically)

**"No shortcuts configured"**
- Run `Soundpad-config.py` to set up keyboard shortcuts
- Ensure categories were imported via `Soundpad-setup.py`

**"Permission denied accessing pipe"**
- Run as Administrator if needed (otherwise the tool will try to run itself automatically)
- Check Windows permissions for named pipes is enabled

**Keyboard shortcuts not working**
- Verify shortcuts are not conflicting with other applications
- Check that keyboard library installed correctly
- **IMPORTANT**: Run as Administrator for global keyboard hooks to work properly (otherwise the tool will try to run itself automatically)

## File Structure

```
Soundpad-commander/
├── Soundpad/
│   ├── __init__.py
│   ├── soundpad_client.py     # Soundpad API wrapper
│   ├── keyboard_listener.py   # Global hotkey handling (keyboard library)
│   ├── config_manager.py      # YAML config management
│   └── file_scanner.py        # Directory scanning
├── 1- Soundpad-setup.py       # Setup tool (moved from bin/)
├── 2- Soundpad-config.py      # Configuration tool (moved from bin/) 
├── 3- Soundpad-run.py         # Main application (moved from bin/)
├── Soundpad-config.yaml       # User configuration (generated)
├── requirements.txt           # Python dependencies
└── README.md                  # Documentation
```

## API Integration

Soundpad Commander uses Soundpad's Named Pipe API for communication:

- **Pipe Path**: `\\.\pipe\sp_remote_control`
- **Protocol**: Text-based commands with HTTP-style responses
- **Key Commands**: 
  - `DoPlayRandomSoundFromCategory(categoryIndex, speakers, microphone)`
  - `DoTogglePause()` - **Used for pause/resume functionality instead of stop**
  - `DoStopSound()` - Available but not used (we use pause/resume instead)
  - `DoAddCategory(name, parentIndex)`
  - `DoAddSound(url, categoryIndex, position)`

## Development

### Code Structure
- `soundpad_client.py` - Python wrapper for Soundpad's Java API
- `config_manager.py` - YAML configuration management with validation
- `file_scanner.py` - Audio file discovery and categorization
- `keyboard_listener.py` - Global keyboard hooks using keyboard library (more reliable than pynput on Windows)

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- **Soundpad** by Leppsoft for providing the excellent audio management platform
- **Rich** library for beautiful CLI interfaces
- **pynput** library for global keyboard hooks

and claude code :D

---

Useful links:
https://www.leppsoft.com/soundpad/
https://www.leppsoft.com/soundpad/help/manual/tutorial/rc/
https://www.leppsoft.com/soundpad/en/rc/
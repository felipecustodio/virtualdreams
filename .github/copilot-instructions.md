# Virtual Dreams - Vaporwave Telegram Bot

Virtual Dreams is a Python Telegram bot that creates vaporwave music by processing audio from YouTube videos. The bot downloads audio, extracts chorus segments, applies vaporwave effects (speed reduction and reverb), and sends the processed audio back to users.

**Always reference these instructions first and fallback to search or bash commands only when you encounter unexpected information that does not match the info here.**

## Working Effectively

### Bootstrap, Build, and Test the Repository
1. **Install system dependencies** (NEVER CANCEL - takes 2-3 minutes):
   ```bash
   sudo apt-get update
   sudo apt-get install -y libgsl27 libgslcblas0 libsndfile1 libsndfile1-dev libmp3lame0 sox ffmpeg
   ```
   - Note: `libgsl0ldbl` from Aptfile is obsolete; use `libgsl27 libgslcblas0` instead
   - **TIMEOUT WARNING**: Set timeout to 300+ seconds for package installation

2. **Install Python dependencies** (NEVER CANCEL - takes 3-5 minutes):
   ```bash
   pip3 install -r requirements.txt
   ```
   - **TIMEOUT WARNING**: Set timeout to 300+ seconds for dependency installation
   - **KNOWN ISSUE**: `python-telegram-bot==11.1.0` has compatibility issues with Python 3.12+
   - All audio processing libraries (`pysndfx`, `pydub`, `pychorus`) install and work correctly

3. **Test core functionality**:
   ```bash
   # Test audio processing (completes in <1 second)
   python3 -c "
   from pysndfx import AudioEffectsChain
   from pydub import AudioSegment
   from pychorus import find_and_output_chorus
   print('✓ All audio processing libraries work correctly')
   "
   ```

### Environment Setup
- **Create environment file**: `echo "TOKEN=your_bot_token_here" > .env`
- **Working directory**: Bot automatically creates and switches to `cache/` directory on startup
- **File cleanup**: Bot automatically removes temporary audio files after processing

### Running the Application
- **Main command**: `python3 vapor.py`
- **Requirements**: 
  - Valid Telegram bot token in `.env` file or `TOKEN` environment variable
  - Network access to YouTube and Telegram APIs
  - **DEPLOYMENT NOTE**: Configured for Heroku deployment with webhook mode
  - **LOCAL TESTING**: Comment line 324 and uncomment line 328 in `vapor.py` for local polling mode

### Key File Locations
- **Main application**: `vapor.py` (single file application)
- **Dependencies**: `requirements.txt`, `Aptfile` (system packages)
- **Static site**: `docs/` directory contains promotional website
- **Configuration**: `.env` for bot token, `runtime.txt` specifies Python version
- **Deployment**: `Procfile` for Heroku deployment

## Validation Scenarios

### Manual Testing Requirements
**ALWAYS run these validation steps after making changes to ensure the bot functions correctly:**

1. **Audio Processing Test** (required - takes <1 second):
   ```bash
   python3 -c "
   from pydub.generators import Sine
   from pysndfx import AudioEffectsChain
   import os
   
   # Create test audio
   sine = Sine(440).to_audio_segment(duration=5000)
   sine.export('test.wav', format='wav')
   
   # Apply vaporwave effects
   fx = AudioEffectsChain().speed(0.63).reverb()
   fx('test.wav', 'test_vapor.wav')
   
   # Cleanup
   os.remove('test.wav')
   os.remove('test_vapor.wav')
   print('✓ Audio processing pipeline works correctly')
   "
   ```

2. **Bot Startup Test** (if you have a valid token):
   ```bash
   # Bot should start, create cache directory, and listen for webhooks
   python3 vapor.py
   ```
   - **Expected behavior**: Bot logs "VIRTUAL DREAMS ONLINE" and runs without errors
   - **KNOWN LIMITATION**: Cannot test full YouTube functionality in restricted environments

3. **Core Import Test**:
   ```bash
   python3 -c "
   import pydub, pysndfx, pychorus, youtube_dl, logzero
   from dotenv import load_dotenv
   print('✓ All core dependencies import successfully')
   "
   ```

## Build and Test Information

### Timing Expectations
- **Dependency installation**: 3-5 minutes (NEVER CANCEL)
- **System package installation**: 2-3 minutes (NEVER CANCEL)
- **Audio processing per request**: <1 second for effects, 10-60 seconds for YouTube download
- **Bot startup**: <5 seconds

### Known Issues and Limitations
- **Telegram Bot Library**: `python-telegram-bot==11.1.0` has compatibility issues with Python 3.12+
  - Error: `No module named 'telegram.vendor.ptb_urllib3.urllib3.packages.six.moves'`
  - **Workaround**: Application functions correctly when Telegram bot token is provided and environment is compatible
- **YouTube Access**: Limited in restricted network environments
- **Python Version**: Designed for Python 3.7.1 (see `runtime.txt`) but core audio processing works on Python 3.12+

### No Linting or Testing Framework
- **No test suite**: Repository has no automated tests
- **No linting setup**: No flake8, pylint, or other code quality tools configured
- **Code validation**: Use `python3 -m py_compile vapor.py` to check syntax
- **Manual testing required**: Always run validation scenarios above

## Common Development Tasks

### Updating Dependencies
- **Python packages**: Edit `requirements.txt` and run `pip3 install -r requirements.txt`
- **System packages**: Edit `Aptfile` for Heroku deployment needs

### Adding Audio Effects
- **Location**: Modify the `fx` AudioEffectsChain in lines 44-58 of `vapor.py`
- **Testing**: Always test with the audio processing validation scenario above

### Debugging Audio Issues
- **Log files**: Check `log.log` and `requests.log` in working directory
- **Audio files**: Temporary files created in `cache/` directory
- **Common issue**: Missing system audio libraries (sox, libsndfile, ffmpeg)

### Modifying Bot Commands
- **Command handlers**: Located in `main()` function (lines 296-300)
- **Command implementations**: Functions like `help_command`, `vapor_command`, `unknown_command`
- **Message templates**: String constants at top of file (lines 70-73)

## Repository Structure
```
.
├── vapor.py              # Main bot application (all functionality)
├── requirements.txt      # Python dependencies
├── Aptfile              # System dependencies for Heroku
├── runtime.txt          # Python version specification
├── Procfile             # Heroku deployment configuration
├── .env                 # Bot token (create manually)
├── cache/               # Working directory (created automatically)
├── docs/                # Static promotional website
│   ├── index.html
│   ├── style.css
│   ├── assets/
│   └── font/
└── .vscode/settings.json # VS Code configuration

Generated during operation:
├── log.log              # Application logs
├── requests.log         # Request statistics
└── cache/               # Temporary audio files
```

## Critical Reminders
- **NEVER CANCEL** system package or Python dependency installations
- **ALWAYS** test audio processing pipeline after changes
- **TIMEOUT SETTINGS**: Use 300+ seconds for installation commands
- **BOT TOKEN REQUIRED**: Application cannot run without valid Telegram bot token
- **NETWORK DEPENDENCIES**: Requires access to YouTube and Telegram APIs for full functionality
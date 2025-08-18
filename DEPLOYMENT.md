# Deployment Guide

## Current Setup (Legacy + yt-dlp)

The bot is currently configured to run with the legacy python-telegram-bot API but with the modern yt-dlp library for improved security and maintainability.

**Files in use:**
- `vapor.py` - Main bot file (legacy API + yt-dlp)
- `requirements.txt` - Dependencies for current setup
- `Procfile` - Deployment configuration

## Modern Async Setup (Future)

To switch to the fully modernized async version:

1. Replace `requirements.txt` with `requirements_modern.txt`:
   ```bash
   mv requirements.txt requirements_legacy.txt
   mv requirements_modern.txt requirements.txt
   ```

2. Update Procfile to use modern version:
   ```
   web: python vapor_modern.py
   ```

3. Deploy with the new configuration

## Migration Benefits

### Immediate (Current)
- ✅ Security: Updated from deprecated youtube_dl to yt-dlp
- ✅ Reliability: Better video extraction and error handling
- ✅ Compatibility: Works with existing deployment

### Future (Modern Async)
- ⚡ Performance: True async operations for better resource usage
- 🔄 Scalability: Better handling of concurrent requests  
- 🛡️ Future-proof: Latest Telegram Bot API features
- 🔧 Maintainability: Modern code patterns and type hints

## Rollback Plan

If issues occur, you can revert to the original by:
1. Restoring original `requirements.txt` and `vapor.py` from git history
2. The legacy version is preserved for emergency rollbacks

## Testing

To test locally:
```bash
# Current version
pip install -r requirements.txt
python vapor.py

# Modern version  
pip install -r requirements_modern.txt
python vapor_modern.py
```
# Setup Guide

This project requires **one API key** and **ffmpeg** to function properly.

## Required Components

### 1. FFmpeg (Required for Whisper)

**Whisper runs locally and requires ffmpeg to process audio files.**

#### Windows Installation:

**Option 1: Using winget (Recommended)**
```powershell
winget install ffmpeg
```

**Option 2: Using Chocolatey**
```powershell
choco install ffmpeg
```

**Option 3: Manual Installation**
1. Download from: https://www.gyan.dev/ffmpeg/builds/
2. Extract the ZIP file
3. Add the `bin` folder to your system PATH
4. **Restart your terminal/IDE**

**Verify installation:**
```powershell
ffmpeg -version
```

#### macOS:
```bash
brew install ffmpeg
```

#### Linux:
```bash
sudo apt update && sudo apt install ffmpeg
```

---

### 2. OPENROUTER_API_KEY

- **Purpose:** Used for Llama 3.2 3B Instruct model (powers the interviewer and coach agents)
- **Where to get it:** https://openrouter.ai/keys
- **Cost:** Pay-per-use (check OpenRouter pricing for Llama 3.2 3B)
- **Note:** Whisper runs locally (no API key needed)

---

## Setup Methods

### Method 1: Using .env File (Recommended)

1. Create a `.env` file in the project root directory (same level as `pyproject.toml`)

2. Add your key to the file:
   ```
   OPENROUTER_API_KEY=sk-or-your-actual-openrouter-key-here
   ```

3. Save the file. The project will automatically load these keys when you run it.

**Note:** The `.env` file is already in `.gitignore`, so it won't be committed to version control.

---

### Method 2: Windows PowerShell (Temporary - Current Session Only)

Open PowerShell and run:

```powershell
$env:OPENROUTER_API_KEY = "sk-or-your-actual-openrouter-key-here"
```

**Note:** These variables only last for the current PowerShell session. Close the terminal and they're gone.

---

### Method 3: Windows PowerShell (Permanent - System-Wide)

```powershell
[System.Environment]::SetEnvironmentVariable('OPENROUTER_API_KEY', 'sk-or-your-actual-openrouter-key-here', 'User')
```

**Important:** After running these commands, you must:
1. Close your current terminal/IDE
2. Reopen it for the changes to take effect

---

### Method 4: Windows CMD (Permanent - System-Wide)

```cmd
setx OPENROUTER_API_KEY "sk-or-your-actual-openrouter-key-here"
```

**Important:** After running these commands, you must:
1. Close your current terminal/IDE
2. Reopen it for the changes to take effect

---

## Verifying Your Keys Are Set

### Check if keys are loaded (Python):

```python
import os
print("OPENROUTER_API_KEY:", "✓ Set" if os.getenv("OPENROUTER_API_KEY") else "✗ Not set")
```

### Check in PowerShell:

```powershell
$env:OPENROUTER_API_KEY
```

### Check if ffmpeg is installed:

```powershell
ffmpeg -version
```

---

## Troubleshooting

### Error: "OPENROUTER_API_KEY is not set"
- Make sure you've set the `OPENROUTER_API_KEY` environment variable
- If using `.env` file, make sure it's in the project root directory
- If using `setx`, restart your terminal/IDE

### Error: "ffmpeg is not installed or not in your PATH"
- Install ffmpeg using one of the methods above
- After installation, **restart your terminal/IDE**
- Verify installation with: `ffmpeg -version`

### Error: "[WinError 2] The system cannot find the file specified" during transcription
- This means ffmpeg is not found. Install ffmpeg and add it to your PATH
- Restart your terminal/IDE after installation

### Keys not loading from .env file
- Make sure `python-dotenv` is installed: `pip install python-dotenv`
- Verify the `.env` file is in the project root (same directory as `pyproject.toml`)
- Check that there are no spaces around the `=` sign in your `.env` file
- Make sure there are no quotes around the values (unless the key itself contains quotes)

---

## Security Best Practices

1. **Never commit your `.env` file** - It's already in `.gitignore`
2. **Never share your API keys** - Keep them private
3. **Use different keys for development and production** if possible
4. **Rotate your keys** if you suspect they've been compromised
5. **Set usage limits** on your API accounts to prevent unexpected charges

---

## Getting Your API Keys

### OpenAI API Key:
1. Go to https://platform.openai.com/api-keys
2. Sign in or create an account
3. Click "Create new secret key"
4. Copy the key (you won't be able to see it again!)

### OpenRouter API Key:
1. Go to https://openrouter.ai/keys
2. Sign in or create an account
3. Click "Create Key"
4. Copy the key

---

## Next Steps

Once your keys are set, you can run the project:

```bash
crewai run
```

Or:

```bash
python -m voice_interview_practice_system.main run
```


# Ctrl-Hire - Voice Interview Practice System

Welcome to Ctrl-Hire, an AI-powered voice interview practice system powered by [crewAI](https://crewai.com). This system helps you practice interviews with realistic AI agents that conduct dynamic interviews and provide personalized feedback.

## Features

- **Voice-Based Interaction**: Questions are spoken using Google TTS and displayed as text
- **Speech-to-Text**: Record your answers using Whisper (local transcription)
- **Dynamic Interview Flow**: AI interviewer adapts questions based on your responses
- **Personalized Feedback**: Coach agent analyzes your performance and provides detailed feedback
- **Session Tracking**: All Q&A sessions are saved in JSON format for review

## Installation

Ensure you have Python >=3.10 <3.14 installed on your system. This project uses [UV](https://docs.astral.sh/uv/) for dependency management and package handling, offering a seamless setup and execution experience.

First, if you haven't already, install uv:

```bash
pip install uv
```

Next, navigate to your project directory and install the dependencies:

(Optional) Lock the dependencies and install them by using the CLI command:
```bash
crewai install
```

### FFmpeg Installation (Required for Whisper)

**Whisper requires ffmpeg to process audio files.** Please install ffmpeg before running the project:

#### Windows Installation Options:

**Option 1: Using winget (Recommended)**
```powershell
winget install ffmpeg
```

**Option 2: Using Chocolatey**
```powershell
choco install ffmpeg
```

**Option 3: Manual Installation**
1. Download ffmpeg from: https://www.gyan.dev/ffmpeg/builds/
2. Extract the ZIP file
3. Add the `bin` folder to your system PATH:
   - Open "Environment Variables" in Windows Settings
   - Edit the "Path" variable
   - Add the full path to the `bin` folder (e.g., `C:\ffmpeg\bin`)
4. **Restart your terminal/IDE** for changes to take effect

**Verify installation:**
```powershell
ffmpeg -version
```

#### macOS Installation:
```bash
brew install ffmpeg
```

#### Linux Installation:
```bash
sudo apt update
sudo apt install ffmpeg
```

### API Keys Setup

This project requires **one API key** to function:

1. **OPENROUTER_API_KEY** - Used for Llama 3.1 8B Instruct (interviewer & coach agents)
   - Get your key from: https://openrouter.ai/keys
   - **Note:** Whisper runs locally (no API key needed)

#### Option 1: Using .env file (Recommended)

Create a `.env` file in the project root directory:

```bash
# .env file
OPENROUTER_API_KEY=your_openrouter_api_key_here
```

**Important:** Never commit the `.env` file to version control. It's already in `.gitignore`.

#### Option 2: Using Environment Variables (Windows PowerShell)

```powershell
# Set OpenRouter API key
$env:OPENROUTER_API_KEY = "your_openrouter_api_key_here"
```

#### Option 3: Using Environment Variables (Windows CMD)

```cmd
setx OPENROUTER_API_KEY "your_openrouter_api_key_here"
```

**Note:** After using `setx`, you need to close and reopen your terminal/IDE for the changes to take effect.

### Virtual Environment Setup

1. Create a virtual environment:
```powershell
python -m venv .venv
```

2. Activate the virtual environment:
```powershell
.\.venv\Scripts\Activate.ps1
```

3. Install dependencies:
```powershell
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install playsound==1.2.2
```

## Running the Project

### Using PowerShell Script (Recommended)

```powershell
# Activate virtual environment first
.\.venv\Scripts\Activate.ps1

# Run the interview system
.\run_interview.ps1
```

### Using Python Directly

```powershell
# Activate virtual environment first
.\.venv\Scripts\Activate.ps1

# Set PYTHONPATH and run
$env:PYTHONPATH = "src"
python -m voice_interview_practice_system.main run
```

### Using CrewAI CLI

```bash
$ crewai run
```

## Understanding Your Crew

The system uses two AI agents:

1. **Dynamic Interview Conductor**: Conducts the interview, asks questions, and adapts based on your responses
2. **Interview Performance Coach**: Analyzes your interview performance and provides detailed feedback

All questions and answers are saved in JSON format in the `sessions/` directory for review.

## Support

For support, questions, or feedback regarding Ctrl-Hire or crewAI:
- Visit our [documentation](https://docs.crewai.com)
- Reach out to us through our [GitHub repository](https://github.com/joaomdmoura/crewai)
- [Join our Discord](https://discord.com/invite/X4JWnZnxPb)
- [Chat with our docs](https://chatg.pt/DWjSBZn)

Let's create wonders together with the power and simplicity of crewAI.

# VoiceInterviewPracticeSystem Crew

Welcome to the VoiceInterviewPracticeSystem Crew project, powered by [crewAI](https://crewai.com). This template is designed to help you set up a multi-agent AI system with ease, leveraging the powerful and flexible framework provided by crewAI. Our goal is to enable your agents to collaborate effectively on complex tasks, maximizing their collective intelligence and capabilities.

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

1. **OPENROUTER_API_KEY** - Used for Llama 3.2 3B Instruct (interviewer & coach agents)
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

### Customizing

- Modify `src/voice_interview_practice_system/config/agents.yaml` to define your agents
- Modify `src/voice_interview_practice_system/config/tasks.yaml` to define your tasks
- Modify `src/voice_interview_practice_system/crew.py` to add your own logic, tools and specific args
- Modify `src/voice_interview_practice_system/main.py` to add custom inputs for your agents and tasks

## Running the Project

To kickstart your crew of AI agents and begin task execution, run this from the root folder of your project:

```bash
$ crewai run
```

This command initializes the voice_interview_practice_system Crew, assembling the agents and assigning them tasks as defined in your configuration.

This example, unmodified, will run the create a `report.md` file with the output of a research on LLMs in the root folder.

## Understanding Your Crew

The voice_interview_practice_system Crew is composed of multiple AI agents, each with unique roles, goals, and tools. These agents collaborate on a series of tasks, defined in `config/tasks.yaml`, leveraging their collective skills to achieve complex objectives. The `config/agents.yaml` file outlines the capabilities and configurations of each agent in your crew.

## Support

For support, questions, or feedback regarding the VoiceInterviewPracticeSystem Crew or crewAI.
- Visit our [documentation](https://docs.crewai.com)
- Reach out to us through our [GitHub repository](https://github.com/joaomdmoura/crewai)
- [Join our Discord](https://discord.com/invite/X4JWnZnxPb)
- [Chat with our docs](https://chatg.pt/DWjSBZn)

Let's create wonders together with the power and simplicity of crewAI.

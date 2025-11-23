## Ctrl+Hire – Voice Interview Practice System

Ctrl+Hire is a **voice‑first interview practice app** where:

- An **AI interviewer** speaks questions using Google TTS and adapts follow‑ups based on your answers.
- You answer by **speaking in your browser** (or typing, if you prefer); responses are transcribed with local Whisper.
- A **coach agent** analyzes the full session and gives structured, actionable feedback.

Built with **CrewAI**, **LLaMA 3.1 8B via OpenRouter**, **Whisper**, **gTTS**, and a custom **Streamlit** frontend.

---

## Table of Contents

- [Features](#features)
- [Demo Scenarios & Evaluation](#demo-scenarios--evaluation)
- [Architecture Overview](#architecture-overview)
- [Agents & Prompt Design](#agents--prompt-design)
- [Voice & Audio Pipeline](#voice--audio-pipeline)
- [Frontend UX Flow](#frontend-ux-flow)
- [Project Structure](#project-structure)
- [Installation & Setup](#installation--setup)
- [Running the Project](#running-the-project)
- [Design Decisions](#design-decisions)
- [Troubleshooting](#troubleshooting)
- [Future Improvements](#future-improvements)

---

## Features

- **Natural interviewer flow**
  - Uses LLaMA 3.1 8B via OpenRouter.
  - Avoids repeating questions or over‑explaining “round names”.
  - Asks short, focused questions that build on your previous answers.

- **Voice‑first interaction**
  - Questions are spoken via Google TTS (slightly sped up with ffmpeg for natural pacing).
  - Answers are recorded through the browser mic or (in CLI mode) system mic.
  - Local Whisper (`openai-whisper`) handles speech‑to‑text.

- **Session tracking**
  - Each interview run is stored as a **single JSON file** in `src/sessions/`.
  - Contains:
    - Candidate profile
    - Ordered Q&A (`qa_list`)
    - Final coach feedback
  - Audio is **not** stored long‑term; only text lives in the sessions.

- **Coach feedback dashboard**
  - Overall narrative summary.
  - Numeric scores (1–5) for:
    - Communication
    - STAR structure
    - Role knowledge
    - Confidence
  - Bullet‑point strengths & improvement areas.
  - Optional per‑round notes (warmup, behavioral, role‑specific, etc.).

- **Modern Streamlit UI**
  - Hero landing section with branding and description.
  - Main‑page profile form (no cluttered sidebar inputs).
  - Interviewer view with a **bot avatar** and spoken questions.
  - Simple answer section: **speak or type, then automatically advance**.

---

## Demo Scenarios & Evaluation

The system is tuned and documented against the following evaluation criteria:

### Conversational Quality

- **Confused User** (unsure what they want)
  - If the latest answer is unclear, contradictory, or off‑topic, the interviewer:
    - Asks **one short clarifying question**,
    - Briefly restates what type of answer they’re looking for in simple language.

- **Efficient User** (wants quick results)
  - Questions are:
    - Short and to the point.
    - Strictly free of repeated greetings and intros.
    - Limited to 1–2 sub‑questions per turn.

- **Chatty User** (goes off topic)
  - The interviewer acknowledges long answers, then:
    - Politely refocuses on a **single concrete follow‑up**,
    - Avoids getting lost in too many branches.

- **Edge Case User**
  - For users who:
    - Refuse to answer,
    - Ask the AI questions instead,
    - Provide obviously impossible information,
  - The interviewer:
    - Responds calmly,
    - Sets expectations about what it can / cannot do,
    - Redirects back to a meaningful interview question.

### Agentic Behaviour & Adaptability

- Uses `conversation_state.qa_list` and `latest_answer` to:
  - Decide whether to clarify, follow up, or move to a new topic.
  - Avoid asking the same question multiple times.
- The coach agent:
  - **Only** comments on questions and answers actually present in `qa_list`.
  - Clearly states when feedback is based on a short or incomplete interview.

---

## Architecture Overview

At a high level, Ctrl+Hire consists of:

- **Frontend**: `streamlit_app.py`
  - Handles UI, browser microphone, and interaction flow.
- **Core logic / CLI**: `main.py`
  - Implements the voice interview loop and session JSON logging.
- **Agents & orchestration**: `crew.py` + `config/`
  - Defines interviewer and coach agents, tasks, and JSON schemas.
- **Persistence**: `src/sessions/`
  - Stores one JSON per interview session.

The LLM stack runs via **OpenRouter** using the `openai` Python client, so switching models is as simple as changing the model name in `main.py` / `crew.py`.

---

## Agents & Prompt Design

### Dynamic Interview Conductor

- Role: conversational interviewer.
- Model: `meta-llama/llama-3.1-8b-instruct`.
- Key prompt constraints (in `_build_dynamic_interview_prompt`):

  - Use `conversation_state.qa_list` to understand history.
  - Do **not** repeat previously asked questions.
  - For follow‑ups:
    - At most two on the same project/topic, then move on.
  - **Conversation quality rules**:
    - For unclear/off‑topic answers, ask one clarifying question.
    - For confused users, restate expectations simply.
    - For chatty users, acknowledge then narrow down.
    - For edge cases, respond calmly, set expectations, and redirect.
  - **Style rules**:
    - No “Hi/Hello/Hey/Good morning” at the start of questions.
    - No re‑introducing the persona or company after the first intro.
    - No explicit “this is a warmup/ice‑breaker/first question” phrases.
    - Round names belong only in `next_round`, not in the spoken question.

- Decoding:
  - `temperature=0.6`, `top_p=0.9`, `max_tokens=600` for natural but focused replies.

### Interview Performance Coach

- Role: performance coach summarizing and scoring your interview.
- Model: same LLaMA 3.1 8B via OpenRouter.
- Prompt (in `_build_coach_prompt`) instructs the agent to:
  - Ground **all** statements strictly in the provided `qa_list`.
  - Avoid inventing questions, rounds, or detailed answers that never occurred.
  - Be explicit when the evaluation is based on very few questions.

- Output schema: defined in `config/analyze_interview_performance.json`, including:
  - `overall_summary`
  - `dimension_scores`
  - `strengths`
  - `improvement_areas`
  - Optional: `per_round_feedback`, `sample_improved_answers`

- Decoding:
  - `temperature=0.4`, `top_p=0.9`, `max_tokens=900` for stable, structured feedback.

---

## Voice & Audio Pipeline

1. **Text‑to‑Speech (Questions & Intro)**
   - Implemented via `gTTS`:
     - `slow=False` for natural speed.
   - Post‑processed with `ffmpeg` when available:
     - Uses `atempo=1.2` to make the voice slightly faster/more conversational.
   - In the CLI mode, audio is played using:
     - `playsound` (if available) or OS‑level commands (`os.startfile`, etc.).
   - In Streamlit, the audio is:
     - Converted to MP3 bytes and played with a hidden `<audio autoplay>` element.

2. **Speech‑to‑Text (User Answers)**
   - Local **Whisper** (`openai-whisper`) with ffmpeg.
   - In Streamlit:
     - Browser mic → `streamlit-mic-recorder` → temporary WAV file → Whisper → text.
   - In CLI:
     - `sounddevice` records directly to WAV → Whisper → text.
   - Audio files are deleted immediately after transcription; only text goes into the JSON.

---

## Frontend UX Flow

### Landing & Profile

- Hero section:
  - Brand: **Ctrl+Hire**.
  - Tagline: calm, voice‑first interview rehearsal with structured feedback.
- Profile form:
  - Name, target role, experience level, company type.
  - Feedback style: **coaching** or **strict**.
- Button: **Start / reset interview** creates a new JSON session and resets state.

### Interviewer Section

1. **Consent**
   - If you haven’t started yet:
     - Message: “Your interviewer is ready. When you're comfortable, click the button below to begin.”
     - Button: **I’m ready to start the interview**.
   - Between rounds:
     - Message: “When you're ready for the next question, click the button below.”
     - Button: **I’m ready for the next question**.

2. **Question Presentation**
   - On the very first question:
     - Plays a combined clip: short intro + first question.
   - Later questions:
     - Plays the next question only.
   - The UI shows:
     - Bot avatar (medium icon) above the text.
     - `Question: <question text>` below the avatar.

### Your Answer Section

- Browser mic recorder:
  - Start → speak → stop.
  - On stop:
    - Audio is transcribed with Whisper.
    - If successful:
      - Answer is saved to `qa_list`.
      - Phase is updated (`await_next` or `finished`).
      - `st.rerun()` is called so the next‑step UI appears immediately.
- Typed answer (optional):
  - Fallback if transcription fails or you prefer typing.
  - Button: **Submit typed answer**.

### Coach Feedback Section

- Button: **Analyze interview with coach**.
- On click:
  - Calls coach agent with full `qa_list`.
  - Renders:

    - **Overall summary** – multi‑paragraph overview.
    - **Scores (1–5)** – metric tiles for each dimension.
    - **Strengths** – bullet list.
    - **Improvement areas** – bullet list.
    - **Round‑by‑round notes** – headings per round with short paragraphs.

---

## Project Structure

```text
voice_interview_practice_system_v1_crewai-project/
  pyproject.toml
  README.md
  run_interview.ps1
  src/
    sessions/
      <user>_<timestamp>.json        # one file per interview
    voice_interview_practice_system/
      __init__.py
      main.py                        # CLI and core logic
      streamlit_app.py               # Streamlit web UI
      crew.py                        # CrewAI agents & tasks
      config/
        agents.yaml
        tasks.yaml
        conduct_dynamic_interview_session.json
        analyze_interview_performance.json
      tools/
        custom_tool.py
```

---

## Installation & Setup

### 1. Requirements

- Python **3.11.x** (recommended).
- `ffmpeg` installed and on your `PATH`.
- `OPENROUTER_API_KEY` (from `https://openrouter.ai/keys`).

### 2. Virtual environment

```powershell
cd path\to\voice_interview_practice_system_v1_crewai-project

python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -e .
```

### 4. Environment variables

Create a `.env` file in the project root:

```bash
OPENROUTER_API_KEY=your_openrouter_api_key_here
```

Or set it in PowerShell for the current session:

```powershell
$env:OPENROUTER_API_KEY = "your_openrouter_api_key_here"
```

---

## Running the Project

### Streamlit Web App (recommended)

```powershell
.\.venv\Scripts\Activate.ps1
streamlit run src/voice_interview_practice_system/streamlit_app.py
```

Then in your browser:

1. Fill the profile form and click **Start / reset interview**.
2. In **Interviewer**, click **I’m ready to start the interview**.
3. Listen to the question and answer by:
   - Recording with the mic (preferred), or
   - Typing and submitting an answer.
4. Repeat for multiple questions.
5. Click **Analyze interview with coach** to see the feedback dashboard.

### CLI Voice Interview

```powershell
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "src"
python -m voice_interview_practice_system.main run
```

This runs a full voice interview in the terminal, using system audio and mic.

---

## Design Decisions

- **Text‑only sessions**: To protect privacy and reduce storage, only text (questions, answers, feedback) is persisted; raw audio is temporary.
- **Local Whisper**: Eliminates dependency on external STT APIs and keeps audio on your machine.
- **Strict output schemas**: Both interviewer and coach responses are constrained by JSON schemas, making it easier to render, test, and extend.
- **Prompt‑level handling of different user types**: The interviewer is explicitly instructed how to respond to confused, efficient, chatty, and edge‑case users.
- **UI minimalism**: The user sees only what a real candidate would see:
  - Persona text, question, answer tools, and feedback—no debug information like round codes, raw JSON, or transcription logs.

---

## Troubleshooting

- **`APITimeoutError: Request timed out`**
  - OpenRouter may be slow or your network unstable.
  - The OpenRouter client uses a **90‑second timeout**; if issues persist, retry or switch networks.
- **`ffmpeg` errors or “file not found”**
  - Ensure `ffmpeg` is installed and on `PATH`:
    - Windows: `winget install ffmpeg` then restart the terminal.
- **No audio transcribed from mic**
  - Check your browser permissions for microphone access.
  - If transcription is empty, the UI prompts you to type an answer instead.

---

## Future Improvements

- Let users pick interviewer persona / difficulty level from the UI.
- Session history page with multiple past interviews and trend graphs.
- Export coach feedback as a PDF or shareable link.
- Support multiple languages for both TTS and Whisper.

---

Ctrl+Hire is designed to feel like a real conversation with a thoughtful interviewer and coach, not just a set of prompts. Use it to rehearse, reflect, and iteratively improve your interview performance.



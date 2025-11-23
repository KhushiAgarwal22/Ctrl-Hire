
## Ctrl+Hire – Voice Interview Practice System

---

## About the Project

Ctrl+Hire is a **voice‑first, JD‑aware interview practice studio** built for serious prep:

- An **AI interviewer** speaks realistic questions, adapts follow‑ups, and can switch into **JD‑specific mode** to drill only the skills a role actually needs.
- You answer mostly by **speaking in your browser**; local **Whisper** converts your speech to text and stores it as structured Q&A.
- A separate **coach agent** reviews the full session and returns **scored, concrete feedback** plus improved sample answers for coding/SQL questions.

The experience runs in a **Streamlit** web app backed by **CrewAI agents**, **LLaMA 3.1 8B via OpenRouter**, **gTTS**, and **local Whisper**.

Unlike simple “single‑prompt” chatbots, Ctrl+Hire keeps a full **per‑user conversation state** (JSON on disk + Streamlit session state) and uses that to decide:

- What stage of the interview you are in.
- Whether to ask a follow‑up or move on to a new topic.
- How the coach should weight each answer when scoring.

---

## Features

- **Voice‑first interview experience**
  - Interviewer introduces themselves and asks questions using **Google TTS**, with speed/pace tuned via `ffmpeg` for a natural feel.
  - You answer by recording directly from the browser mic (`streamlit-mic-recorder`) or, as a fallback, by typing.
  - Local **Whisper** (`openai-whisper`) handles speech‑to‑text; audio files are deleted after transcription.

- **JD‑specific and general interview modes**
  - **General mode**: full structured interview (warmup, behavioral, role‑specific, culture, wrap‑up) with smart follow‑ups.
  - **JD‑specific mode**: paste a job description and click **Start JD-specific interview** to get:
    - 6–10 questions tightly anchored to the JD’s responsibilities, stack, and domain.
    - Emphasis on **core skills** (languages, frameworks, OS, CN, DB, DSA, system design, analytics tools) and realistic scenarios.
    - Minimal generic behavioral questions; situational prompts are specific to the JD’s environment.
  - The interviewer prompt explicitly enforces that **at least ~70% of JD questions are technical / core‑skill focused**, with only very targeted situational prompts (e.g., debugging a production incident in that stack).

- **Coding / SQL workspaces with function stubs**
  - For DSA / algorithm / SQL questions, the interviewer includes a **Python function or query stub** in the question.
  - The Streamlit app auto‑extracts that stub and pre‑fills a **code editor text area**, so you only complete the body (LeetCode‑style).
  - A dedicated **technical evaluator** LLM call scores correctness and gives a short verdict just for that problem.
  - The technical evaluator does **not** replace the coach; instead, it attaches a compact JSON object to that Q&A entry, which the coach later uses when building the final report.

- **Structured coaching and error explanation**
  - The coach agent produces:
    - Overall summary and 1–5 scores for communication, structure (STAR), role knowledge, and confidence.
    - Strengths, improvement areas, and round‑by‑round notes.
    - For coding/SQL answers: a short explanation of **what went wrong**, plus a corrected snippet in `sample_improved_answers`.
  - Role‑specific feedback highlights how you performed on **technical questions**, not just general soft skills.
  - The coach is instructed to **never invent questions or answers**; everything it says must be grounded in actual entries from `qa_list`, which makes reports trustworthy for post‑analysis.

- **Session logging & JSON schema design**
  - Every session is saved as **one JSON file per user run** under `src/sessions/`:
    - Candidate profile, including optional `job_description`.
    - Ordered `qa_list` with question text, answer text, and optional `technical_evaluation` blocks.
    - Final `coach_feedback` object.
  - Audio is never stored; only **text Q&A + feedback** are persisted.
  - The schemas are designed so that you can later feed the same JSON into:
    - Analytics dashboards (e.g., to plot score trends over time).
    - A recruitment or LMS system.
    - A fine‑tuning or RAG pipeline, if you want to build your own models on top of this data.

- **Modern, Gen‑Z‑friendly UI**
  - Gradient hero card with Ctrl+Hire branding and a short, punchy description.
  - Main‑page profile form (name is mandatory), with **separate buttons** for general vs JD‑specific interviews.
  - Interview tab with:
    - Bot avatar, spoken questions, and clean text display.
    - Auto‑advance after voice answers; minimal buttons and zero backend debug noise.
  - Coach and Session Log tabs for feedback review and quick Q&A inspection.
  - The frontend hides internal metadata like “round names”, raw JSON, or transcription logs so that it feels like a **real interview tool**, not an AI playground.

---

## Usage in Real Life

- **SDE / SWE prep**
  - Practice behavioral + system design + DSA/algorithms, with **code‑stub questions** that resemble LeetCode and GfG.
  - Use JD‑specific mode to tune questions to **backend**, **full‑stack**, or **data‑heavy** roles.
   - Example: paste a JD for a backend SDE at a fintech; the interviewer focuses on REST APIs, database transactions, caching, and concurrency.

- **Data / Analytics roles**
  - Get SQL questions that require writing precise queries over realistic table schemas.
  - Coach explains query issues and suggests a corrected, optimized version.
   - Example: a JD mentioning “Snowflake, dashboards, cohort analysis” leads to questions about window functions, aggregations, and defining metrics.

- **Project‑based storytelling**
  - When you talk about projects, the coach infers **technical strengths** (e.g., “Strong in Kafka streaming and low‑latency APIs”).  

- **Self‑review before interviews**
  - Run one or two mock sessions right before a real interview to surface weak answers.
  - Export or copy key feedback sections as notes for last‑minute revision.
   - Over multiple sessions, you can compare JSONs or scores to see which dimensions (e.g., communication vs depth) are improving.

---

## Tech Stack

- **Frontend**
  - `Streamlit` for the multi‑page web app.
  - `streamlit-mic-recorder` for in‑browser mic capture.

- **LLMs & Agents**
  - `openai` Python client with **OpenRouter** and the model `meta-llama/llama-3.1-8b-instruct`.
  - `CrewAI` for defining agents and tasks.
  - All LLM calls use the **OpenAI‑compatible** Chat Completions API, so you can swap in another provider by changing the `base_url` and `model` name.

- **Audio**
  - `gTTS` for text‑to‑speech.
  - `openai-whisper` for local speech‑to‑text.
  - `ffmpeg` for audio speed adjustment.

- **Backend / Utilities**
  - Python 3.11, `python-dotenv`, `PyYAML`, `sounddevice` (CLI only), and standard libraries.
  - Tests (if you re‑add them) can be run with `pytest` and are written to exercise both CLI and Streamlit helper logic.

---

## Architecture

- **Streamlit Frontend (`streamlit_app.py`)**
  - Renders landing page, profile form, navigation tabs, and microphone / code editor UI.
  - Calls into `main.py` helpers for interviewer, coach, transcription, and evaluation.

- **Core Orchestration (`main.py`)**
  - Builds system prompts (`_build_dynamic_interview_prompt`, `_build_coach_prompt`).
  - Handles JSON session creation, `qa_list` updates, and coach feedback storage.
  - Manages TTS, Whisper transcription, and OpenRouter client setup.
  - Provides a CLI entrypoint (`run()`) so you can run a full voice interview in the terminal without Streamlit.

- **CrewAI Agents 
  - **Dynamic Interview Conductor**
    - Goal: run a human‑like interview that adapts to answers and avoids repetition.
    - Uses `conduct_dynamic_interview_session` task description + JSON schema.
    - Has logic for warmup vs technical vs culture rounds, and a special **JD‑focused mode** that ignores generic rounds.
     - Prompt rules cover:
       - How many follow‑ups to ask on the same topic (usually at most two).
       - How to behave with confused, chatty, or edge‑case users.
       - How to embed **code stubs** into technical questions so the UI can show a ready‑to‑edit function signature.
  - **Interview Performance Coach**
    - Goal: evaluate the finished interview and give grounded, structured feedback.
    - Uses `analyze_interview_performance` task description + JSON schema.
    - Produces scores, strengths, improvement areas, inferred technical skills, and improved answers.
     - Explicitly instructed to:
       - Only comment on questions actually present in `qa_list`.
       - Call out specific problems in technical answers (wrong complexity, missing edge cases, incorrect joins, etc.).
       - Provide a clear “what to do differently next time” section instead of generic platitudes.

- **Inline Technical Evaluator 
  - A dedicated LLaMA call that grades **one coding/SQL answer** with:
    - `is_correct`, `score_0_to_1`, `short_verdict`.
    - `detailed_feedback` and `ideal_answer_outline`.
  - Stored per‑question inside `qa_list` for later coach analysis.

- **Persistence Layer 
  - Flat JSON files; no database required.
  - Designed so you can later import into analytics tools or dashboards.

---

## System Design

- **Flow**
  1. User configures profile and (optionally) pastes a JD on the **Home** page.
  2. Starting an interview creates a **new session JSON** and redirects to the **Interview** tab.
  3. For each turn:
     - Frontend calls `_ask_interviewer_question` → LLaMA returns persona + `next_question` JSON.
     - TTS plays the question; UI shows the bot face and text.
     - User responds via mic or code editor; Whisper or text area captures the answer.
     - `_append_qa_to_session` writes the Q&A into the JSON file and updates `conversation_state`.
  4. When the interviewer sets `end_interview=true`, phase flips to `finished`.
  5. On the **Coach** tab, `_analyze_with_coach` is called with full `qa_list` to generate feedback.

- **Key Design Choices**
  - Stateless LLM calls; **session state is owned by JSON + `st.session_state`**.
  - All AI outputs are constrained by JSON schemas to keep the UI robust.
  - Audio is ephemeral; only text is persisted to make storage and privacy simpler.
  - The system is intentionally **single‑user / single‑session** by default, but the file‑based design makes it easy to:
    - Mount the app behind authentication and map sessions to real users.
    - Sync JSONs to cloud storage or a database for team analytics.

---

## Images
<img width="1919" height="793" alt="image" src="https://github.com/user-attachments/assets/fe2d4948-1488-460e-8d37-781ad075453c" />
<img width="1919" height="785" alt="image" src="https://github.com/user-attachments/assets/fc37429a-1c63-4e91-8f9b-1b1d2b87a138" />
<img width="1911" height="608" alt="image" src="https://github.com/user-attachments/assets/9cbbc6ca-61b0-4869-8d76-bae0ae003a5c" />
<img width="1892" height="873" alt="image" src="https://github.com/user-attachments/assets/dca1481d-d699-4b82-9257-9c9ecfc8ae6a" />




---

## File Structure

```text
voice_interview_practice_system_v1_crewai-project/
  pyproject.toml
  README.md
  run_interview.ps1 / run_interview.bat
  src/
    sessions/
      <user>_<timestamp>.json          # one file per interview
    voice_interview_practice_system/
      __init__.py
      main.py                          # core logic, TTS/STT, LLM prompts, JSON sessions
      streamlit_app.py                 # Streamlit web UI and interaction flow
      crew.py                          # CrewAI agents and tasks
      config/
        agents.yaml
        tasks.yaml
        conduct_dynamic_interview_session.json
        analyze_interview_performance.json
      tools/                           # (optional) custom tools for crews
```

---

## Complete Setup Guide

### 1. Prerequisites

- **Python**: 3.11.x (recommended).
- **ffmpeg** installed and on your `PATH` (required by Whisper and audio utilities).
- **OpenRouter account** and `OPENROUTER_API_KEY` from `https://openrouter.ai/keys`.

### 2. Clone and create a virtual environment

```powershell
cd path\to\
git clone https://github.com/<your-username>/voice_interview_practice_system_v1_crewai-project.git
cd voice_interview_practice_system_v1_crewai-project

python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

On macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -e .
```

### 4. Configure environment variables

Create a `.env` file in the project root:

```bash
OPENROUTER_API_KEY=your_openrouter_api_key_here
```

Or set it per‑session (PowerShell example):

```powershell
$env:OPENROUTER_API_KEY = "your_openrouter_api_key_here"
```

### 5. Run the Streamlit web app (recommended)

```powershell
.\.venv\Scripts\Activate.ps1   # or source .venv/bin/activate on macOS/Linux
streamlit run src/voice_interview_practice_system/streamlit_app.py
```

In your browser:

1. On **Home**, enter your name, role, experience level, and company type.
2. Optionally paste a **job description** and click **Start JD-specific interview**, or click **Start general interview**.
3. On the **Interview** tab, let the interviewer speak the question and respond using the mic or (for coding) via the code editor.
4. After a few questions, open the **Coach** tab and click **Analyze interview with coach**.
5. Use the **Session log** tab to quickly inspect the questions asked in the current session.

### 6. Optional: CLI voice interview

```powershell
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "src"
python -m voice_interview_practice_system.main run
```

This runs a pure terminal‑based voice interview using system audio and microphone, writing JSON sessions the same way as the web app.

---

Ctrl+Hire is built to feel like a real conversation with a thoughtful interviewer and coach, while still giving you structured data and feedback you can learn from or plug into your own analytics. Use it as a personal mock interview studio or as a building block for a larger assessment platform.

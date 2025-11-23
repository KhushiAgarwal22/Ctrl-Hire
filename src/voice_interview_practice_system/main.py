#!/usr/bin/env python
import json
import os
import sys
import subprocess
import platform
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import sounddevice as sd
import soundfile as sf
from dotenv import load_dotenv
from gtts import gTTS
from openai import OpenAI
import whisper
import yaml
import time

# Optional playsound support: if available, used for in-process audio playback.
try:  # pragma: no cover - playsound is optional and may not be installed
    from playsound import playsound  # type: ignore[import-not-found]
except Exception:  # pragma: no cover
    playsound = None  # type: ignore[assignment]

from voice_interview_practice_system.crew import VoiceInterviewPracticeSystemCrew

# Load environment variables from .env file if it exists
load_dotenv()


BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"
SESSIONS_DIR = BASE_DIR.parent / "sessions"


def _ensure_sessions_dir() -> None:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def _load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _play_audio_file(filepath: Path) -> bool:
    """
    Play an audio file.
    - First try playsound (if installed and working)
    - Then fall back to OS-level mechanisms so audio is actually heard.
    Returns True if playback was triggered, False otherwise.
    """
    # 1) Try in-process playback with playsound if available
    if playsound is not None:  # pragma: no cover - optional / env-dependent
        try:
            playsound(str(filepath))
            return True
        except Exception:
            # Fall through to OS-level playback
            pass

    # 2) OS-level fallback
    try:
        system = platform.system()
        if system == "Windows":
            # Use os.startfile when available (Windows only)
            if hasattr(os, "startfile"):
                os.startfile(str(filepath))  # type: ignore[attr-defined]
                return True
            # Fallback to PowerShell Start-Process
            subprocess.run(
                [
                    "powershell",
                    "-Command",
                    f'Start-Process \"{str(filepath)}\"',
                ],
                check=False,
            )
            return True
        elif system == "Darwin":
            # macOS: use afplay
            subprocess.run(["afplay", str(filepath)], check=False)
            return True
        else:
            # Linux / others: try xdg-open
            subprocess.run(["xdg-open", str(filepath)], check=False)
            return True
    except Exception:
        return False


def _speed_up_tts_audio_if_possible(src: Path, speed: float = 1.2) -> Path:
    """
    Use ffmpeg (if available) to slightly speed up the TTS audio for a more natural pace.
    Returns the path to the (possibly) processed file.
    """
    if speed <= 1.0:
        return src

    # Reuse ffmpeg availability check used by Whisper
    if not _check_ffmpeg_available():
        return src

    dst = src.with_name(src.stem + "_fast" + src.suffix)
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(src),
                "-filter:a",
                f"atempo={speed}",
                str(dst),
            ],
            check=True,
            capture_output=True,
        )
        return dst
    except Exception:
        # If anything fails, fall back to the original audio
        return src


def _speak_text_google_tts(text: str, filename: Optional[Path] = None) -> None:
    """
    Use Google TTS (gTTS) to synthesize the interviewer question and play it.
    """
    if not text:
        return

    # Use a temp directory so question audio is not persisted in sessions
    if filename is None:
        tmp_dir = Path(tempfile.gettempdir())
        # Use a unique file per call to avoid "Permission denied" if a previous
        # player still has the file open.
        ts = int(time.time() * 1000)
        filename = tmp_dir / f"voice_interview_question_{ts}.mp3"

    try:
        tts = gTTS(text=text, lang="en", slow=False)
        tts.save(str(filename))

        # Optionally speed up playback slightly for a more conversational pace
        processed = _speed_up_tts_audio_if_possible(filename, speed=1.2)

        # Try to play the audio
        played = _play_audio_file(processed)
        if not played:
            print(f"[INFO] Audio file saved to {filename} (could not play automatically)")

        # Always print the text as well
        print(f"[TEXT] {text}")
    except Exception as e:
        print(f"[WARN] Failed to generate/play audio with Google TTS: {e}")
        print(f"[FALLBACK] Question (text only): {text}")


def _record_audio_to_file(
    filename: Path,
    duration_seconds: int = 90,
    sample_rate: int = 16_000,
    channels: int = 1,
) -> bool:
    """
    Record audio from the default microphone into a WAV file.
    Returns True on success, False if recording failed.
    Supports early stopping with Ctrl+C.
    """
    import time
    
    print(f"\nPress Enter to start recording (up to {duration_seconds} seconds)...")
    print("(Press Ctrl+C to stop recording early)")
    input()
    print("Recording... speak now. (Press Ctrl+C when done)")
    
    frames = None
    try:
        # Start recording in non-blocking mode
        frames = sd.rec(
            int(duration_seconds * sample_rate),
            samplerate=sample_rate,
            channels=channels,
            blocking=False,
        )
        
        # Poll for completion - this allows Ctrl+C to interrupt
        # Check if recording is still active by polling the stream status
        try:
            while True:
                # Check if recording is done
                if not sd.get_stream().active:
                    break
                # Small sleep allows Ctrl+C to be caught
                time.sleep(0.1)
        except (AttributeError, RuntimeError):
            # Fallback: just wait for the full duration
            # But use sleep in a loop so Ctrl+C can interrupt
            elapsed = 0
            while elapsed < duration_seconds:
                time.sleep(0.1)
                elapsed += 0.1
        
        # Recording completed normally
        sf.write(str(filename), frames, sample_rate)
        print(f"Recording saved to: {filename}")
        return True
        
    except KeyboardInterrupt:
        print("\n[INFO] Recording stopped by user.")
        try:
            # Stop the recording stream immediately
            sd.stop()
            
            # Wait a brief moment for the stream to finish writing
            time.sleep(0.3)
            
            # Save what we have so far
            if frames is not None:
                sf.write(str(filename), frames, sample_rate)
                print(f"Partial recording saved to: {filename}")
                return True
        except Exception as e:
            print(f"[WARN] Could not save partial recording: {e}")
        return False
    except Exception as e:
        print(f"[WARN] Audio recording failed: {e}")
        try:
            sd.stop()
        except Exception:
            pass
        return False


_whisper_model: Optional["whisper.Whisper"] = None


def _check_ffmpeg_available() -> bool:
    """
    Check if ffmpeg is available in the system PATH.
    Whisper requires ffmpeg to process audio files.
    """
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _get_whisper_model() -> "whisper.Whisper":
    """
    Load (or reuse) the local Whisper model for transcription.
    """
    global _whisper_model
    if _whisper_model is None:
        # You can change 'base' to 'small', 'medium', etc. depending on your hardware
        _whisper_model = whisper.load_model("base")
    return _whisper_model


def _transcribe_with_whisper(audio_path: Path) -> str:
    """
    Transcribe recorded audio using local Whisper (no cloud API).
    Requires ffmpeg to be installed and in PATH.
    """
    # Check for ffmpeg first
    if not _check_ffmpeg_available():
        print("\n[ERROR] ffmpeg is not installed or not in your PATH.")
        print("[INFO] Whisper requires ffmpeg to process audio files.")
        print("[INFO] Please install ffmpeg:")
        print("  - Windows: Download from https://www.gyan.dev/ffmpeg/builds/")
        print("            Extract and add the 'bin' folder to your PATH")
        print("  - Or use: winget install ffmpeg")
        print("  - Or use: choco install ffmpeg (if you have Chocolatey)")
        print("  - After installation, restart your terminal/IDE")
        print("\n[INFO] Fallback: You can type your answer manually when prompted.")
        return ""
    
    try:
        # Ensure we have an absolute path
        audio_path_abs = audio_path.resolve()
        
        # Check if file exists
        if not audio_path_abs.exists():
            print(f"[ERROR] Audio file not found: {audio_path_abs}")
            return ""
        
        # Check if file is readable
        if not os.access(audio_path_abs, os.R_OK):
            print(f"[ERROR] Audio file is not readable: {audio_path_abs}")
            return ""
        
        model = _get_whisper_model()
        # Use absolute path as string for Whisper
        try:
            result = model.transcribe(str(audio_path_abs))
        except KeyboardInterrupt:
            # Gracefully handle user cancelling a long transcription
            print("\n[INFO] Transcription cancelled by user (Ctrl+C).")
            return ""

        text = (result.get("text") or "").strip()
        print(f"\n[Transcription] {text}\n")
        return text
    except FileNotFoundError as e:
        print(f"[ERROR] Local Whisper transcription failed - file not found: {e}")
        print(f"[INFO] Make sure ffmpeg is installed and in your PATH.")
        print(f"[INFO] Download ffmpeg from: https://ffmpeg.org/download.html")
        return ""
    except Exception as e:
        error_msg = str(e)
        if "ffmpeg" in error_msg.lower() or "winerror 2" in error_msg.lower():
            print(f"[ERROR] Local Whisper transcription failed: {e}")
            print(f"[INFO] Whisper requires ffmpeg to process audio files.")
            print(f"[INFO] Please install ffmpeg and add it to your PATH.")
            print(f"[INFO] Windows: Download from https://www.gyan.dev/ffmpeg/builds/")
            print(f"[INFO] Or use: winget install ffmpeg")
        else:
            print(f"[ERROR] Local Whisper transcription failed: {e}")
        return ""


def _get_openrouter_client() -> OpenAI:
    """
    Create an OpenRouter client (OpenAI-compatible) using OPENROUTER_API_KEY.
    Used for Llama 3.2 3B Instruct chat completions.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Please export it to use OpenRouter."
        )
    try:
        # Increase timeout so lengthy LLM generations don't fail abruptly.
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            timeout=90,  # seconds
        )
        return client
    except Exception as e:
        raise RuntimeError(f"Failed to initialize OpenRouter client: {e}") from e


def _build_dynamic_interview_prompt(
    agents_cfg: Dict[str, Any],
    tasks_cfg: Dict[str, Any],
) -> str:
    agent_cfg = agents_cfg.get("dynamic_interview_conductor", {})
    task_cfg = tasks_cfg.get("conduct_dynamic_interview_session", {})

    role = agent_cfg.get("role", "Dynamic Interview Conductor")
    goal = agent_cfg.get("goal", "")
    backstory = agent_cfg.get("backstory", "")
    description = task_cfg.get("description", "")
    expected_output = task_cfg.get("expected_output", "")

    system_prompt = (
        f"You are the '{role}'.\n\n"
        f"GOAL:\n{goal}\n\n"
        f"BACKSTORY:\n{backstory}\n\n"
        f"TASK DESCRIPTION:\n{description}\n\n"
        f"OUTPUT FORMAT INSTRUCTIONS:\n{expected_output}\n\n"
        "Always respond as a single JSON object compatible with the described output format. "
        "Do not include any explanatory text outside of the JSON.\n\n"
        "Use the provided 'conversation_state.qa_list' to understand what has already been asked and "
        "how the candidate answered. Do not repeat questions that have already been asked, and avoid "
        "rephrasing the same question multiple times. Limit follow-up questions on the same project or "
        "topic to at most two before moving on to a new, distinct topic relevant to the candidate_profile.\n\n"
        "IMPORTANT STYLE RULES FOR QUESTIONS:\n"
        "- The interviewer persona will introduce themselves separately at the start of the interview.\n"
        "- Do NOT start questions with greetings like 'Hi', 'Hello', 'Hey', 'Good morning', etc.\n"
        "- Do NOT re-introduce yourself or restate your role/company once the persona has been shared.\n"
        "- Do NOT mention that a question is an 'icebreaker', 'warm-up', or similar; simply ask it.\n"
        "- Do NOT mention the round name (warmup, technical, etc.) or meta labels like 'first question' inside next_question.text; "
        "that information belongs only in the 'next_round' field.\n"
        "- Begin each question directly with the content of the question, as a normal interviewer would do after the initial greeting.\n"
        "- Keep each question conversational and natural, avoiding long multi-part prompts; at most 1–2 closely related sub-questions."
    )
    return system_prompt


def _build_coach_prompt(
    agents_cfg: Dict[str, Any],
    tasks_cfg: Dict[str, Any],
) -> str:
    agent_cfg = agents_cfg.get("interview_performance_coach", {})
    task_cfg = tasks_cfg.get("analyze_interview_performance", {})

    role = agent_cfg.get("role", "Interview Performance Coach")
    goal = agent_cfg.get("goal", "")
    backstory = agent_cfg.get("backstory", "")
    description = task_cfg.get("description", "")
    expected_output = task_cfg.get("expected_output", "")

    system_prompt = (
        f"You are the '{role}'.\n\n"
        f"GOAL:\n{goal}\n\n"
        f"BACKSTORY:\n{backstory}\n\n"
        f"TASK DESCRIPTION:\n{description}\n\n"
        f"OUTPUT FORMAT INSTRUCTIONS:\n{expected_output}\n\n"
        "Always respond as a single JSON object compatible with the described output format. "
        "Do not include any explanatory text outside of the JSON.\n\n"
        "When generating feedback, base ALL observations and suggestions strictly on the actual "
        "question-answer pairs provided in qa_list. Quote or paraphrase specific answers where helpful. "
        "Do NOT invent additional questions, answers, rounds, or topics that do not appear in qa_list.\n"
        "- If there was only 1 question, clearly state that the evaluation is based on a single question and "
        "do NOT describe performance on other hypothetical questions.\n"
        "- The per_round_feedback object MUST only include keys for rounds that actually appear in qa_list "
        "(based on each entry's 'round' field). Do not add feedback for rounds that never occurred.\n"
        "- If qa_list is short, it is better to say that the evaluation is limited than to imagine missing parts."
    )
    return system_prompt


def _ask_interviewer_question(
    client: OpenAI,
    system_prompt: str,
    model: str,
    candidate_profile: Dict[str, Any],
    conversation_state: Dict[str, Any],
    latest_answer: str,
) -> Dict[str, Any]:
    """
    Call a LLaMA 3.x ~7–8B Instruct model via OpenRouter to get the next
    interviewer question in structured JSON.
    """
    user_payload = {
        "candidate_profile": candidate_profile,
        "conversation_state": conversation_state,
        "latest_answer": latest_answer,
    }

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload)},
        ],
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {
            "persona": None,
            "next_round": "unknown",
            "next_question": {
                "question_type": "generic",
                "skill_tags": [],
                "text": content,
            },
            "end_interview": False,
        }


def _analyze_with_coach(
    client: OpenAI,
    system_prompt: str,
    model: str,
    candidate_profile: Dict[str, Any],
    qa_list: List[Dict[str, Any]],
    feedback_mode: str,
) -> Dict[str, Any]:
    """
    Call LLaMA 3.3 70B Instruct via OpenRouter with the coach prompt to
    analyze the full interview.
    """
    user_payload = {
        "candidate_profile": candidate_profile,
        "qa_list": qa_list,
        "feedback_mode": feedback_mode,
    }

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload)},
        ],
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"raw_feedback": content}


def _start_voice_interview_session() -> None:
    """
    Run an interactive, voice-based interview session:
    - Interviewer asks questions via Google TTS (and prints text)
    - User records answers via microphone; audio is transcribed with Whisper
    - All Q&A pairs are appended to a per-session JSON file
    - At the end, the coach agent analyzes the session and appends feedback
    """
    _ensure_sessions_dir()

    print("=== Voice Interview Practice System ===\n")
    user_name = input("Your name: ").strip() or "anonymous"
    target_role = input("Target role (e.g., SDE, Data Analyst, PM): ").strip()
    experience_level = input("Experience level (e.g., junior, mid, senior): ").strip()
    company_type = input("Company type (e.g., Big Tech, startup, enterprise): ").strip()
    feedback_mode = input("Feedback mode (strict/coaching): ").strip() or "coaching"

    candidate_profile = {
        "user_name": user_name,
        "target_role": target_role,
        "experience_level": experience_level,
        "company_type": company_type,
    }

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in user_name)
    session_filename = f"{safe_name or 'candidate'}_{timestamp}.json"
    session_path = SESSIONS_DIR / session_filename

    session_data: Dict[str, Any] = {
        "candidate_profile": candidate_profile,
        "feedback_mode": feedback_mode,
        "qa_list": [],
        "interviewer_persona": None,
        "created_at_utc": timestamp,
    }

    agents_cfg = _load_yaml(CONFIG_DIR / "agents.yaml")
    tasks_cfg = _load_yaml(CONFIG_DIR / "tasks.yaml")

    dynamic_system_prompt = _build_dynamic_interview_prompt(agents_cfg, tasks_cfg)
    coach_system_prompt = _build_coach_prompt(agents_cfg, tasks_cfg)

    # OpenRouter client runs a larger Llama 3.x (~7–8B) model for interviewer + coach
    openrouter_client = _get_openrouter_client()
    chat_model = "meta-llama/llama-3.1-8b-instruct"

    conversation_state: Dict[str, Any] = {"qa_list": []}
    latest_answer_text = ""
    interviewer_persona: Optional[str] = None

    print(f"\nSession JSON will be saved to: {session_path}\n")
    turn_index = 0
    while True:
        turn_index += 1
        print(f"\n--- Interview Turn {turn_index} ---")

        question_struct = _ask_interviewer_question(
            client=openrouter_client,
            system_prompt=dynamic_system_prompt,
            model=chat_model,
            candidate_profile=candidate_profile,
            conversation_state=conversation_state,
            latest_answer=latest_answer_text,
        )

        persona = question_struct.get("persona")
        if persona and not interviewer_persona:
            interviewer_persona = persona
            session_data["interviewer_persona"] = persona
            print(f"\n[Interviewer Persona] {persona}\n")

            # Let the interviewer introduce itself using its persona, via voice.
            intro_voice = (
                f"Hello {user_name or 'there'}. "
                f"My name is {persona}. "
                f"I will be your interviewer for the {target_role or 'selected'} role. "
                "I will ask you questions and listen to your answers. "
                "Let us begin."
            )
            _speak_text_google_tts(intro_voice)

        next_round = question_struct.get("next_round", "unknown")
        next_question_obj = question_struct.get("next_question", {}) or {}
        question_text = next_question_obj.get("text", "Please answer this question.")
        end_interview = bool(question_struct.get("end_interview", False))

        print(f"[Round] {next_round}")
        print(f"[Question] {question_text}\n")

        _speak_text_google_tts(question_text)

        # Record answer to a temporary audio file (not persisted in sessions)
        tmp_dir = Path(tempfile.gettempdir())
        audio_filename = tmp_dir / f"voice_interview_{safe_name or 'candidate'}_{timestamp}_turn{turn_index}.wav"
        recorded = _record_audio_to_file(audio_filename)

        try:
            if recorded:
                answer_text = _transcribe_with_whisper(audio_filename)
                # If Whisper did not return anything (or was cancelled), fall back to manual input
                if not answer_text.strip():
                    print("[INFO] No transcription captured. You can type your answer instead.")
                    answer_text = input("Please type your answer (fallback): ").strip()
            else:
                answer_text = input("Please type your answer (fallback): ").strip()
        finally:
            # Best-effort cleanup: do not keep answer recordings on disk
            try:
                if audio_filename.exists():
                    audio_filename.unlink()
            except Exception:
                pass

        latest_answer_text = answer_text

        # Only store text in the session JSON (no audio file paths)
        qa_entry = {
            "turn": turn_index,
            "round": next_round,
            "question": question_text,
            "answer_text": answer_text,
        }
        session_data["qa_list"].append(qa_entry)
        conversation_state["qa_list"] = session_data["qa_list"]

        with session_path.open("w", encoding="utf-8") as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)

        if end_interview:
            print("\n[System] Interview has concluded according to the interviewer agent.\n")
            break

        user_continue = input("Press Enter to continue to the next question (or type 'q' to quit): ").strip().lower()
        if user_continue == "q":
            print("Ending interview early by user request.\n")
            break

    print("\n=== Analyzing your performance with the coach agent ===\n")
    coach_feedback = _analyze_with_coach(
        client=openrouter_client,
        system_prompt=coach_system_prompt,
        model=chat_model,
        candidate_profile=candidate_profile,
        qa_list=session_data["qa_list"],
        feedback_mode=feedback_mode,
    )

    session_data["coach_feedback"] = coach_feedback
    with session_path.open("w", encoding="utf-8") as f:
        json.dump(session_data, f, ensure_ascii=False, indent=2)

    print("Coach feedback (JSON):")
    print(json.dumps(coach_feedback, ensure_ascii=False, indent=2))


def run() -> None:
    """
    Entry point used by `crewai run`:
    Launch an interactive voice-based interview session.
    """
    _start_voice_interview_session()


def train() -> None:
    """
    Retain the original crewAI training entrypoint (non-voice).
    """
    inputs = {
        "target_role": "SDE",
        "experience_level": "mid",
        "company_type": "startup",
        "feedback_mode": "coaching",
    }
    try:
        VoiceInterviewPracticeSystemCrew().crew().train(
            n_iterations=int(sys.argv[1]),
            filename=sys.argv[2],
            inputs=inputs,
        )
    except Exception as e:
        raise Exception(f"An error occurred while training the crew: {e}")


def replay() -> None:
    """
    Replay the crew execution from a specific task (non-voice).
    """
    try:
        VoiceInterviewPracticeSystemCrew().crew().replay(task_id=sys.argv[1])
    except Exception as e:
        raise Exception(f"An error occurred while replaying the crew: {e}")


def test() -> None:
    """
    Test the crew execution and return the results (non-voice).
    """
    inputs = {
        "target_role": "SDE",
        "experience_level": "mid",
        "company_type": "startup",
        "feedback_mode": "coaching",
    }
    try:
        VoiceInterviewPracticeSystemCrew().crew().test(
            n_iterations=int(sys.argv[1]),
            openai_model_name=sys.argv[2],
            inputs=inputs,
        )
    except Exception as e:
        raise Exception(f"An error occurred while testing the crew: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: main.py <command> [<args>]")
        sys.exit(1)

    command = sys.argv[1]
    if command == "run":
        run()
    elif command == "train":
        train()
    elif command == "replay":
        replay()
    elif command == "test":
        test()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)



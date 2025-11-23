import base64
import json
import re
import tempfile
import time
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st
from gtts import gTTS
from streamlit_mic_recorder import mic_recorder

from voice_interview_practice_system.main import (  # type: ignore[import-not-found]
    CONFIG_DIR,
    SESSIONS_DIR,
    _analyze_with_coach,
    _ask_interviewer_question,
    _build_coach_prompt,
    _build_dynamic_interview_prompt,
    _ensure_sessions_dir,
    _get_openrouter_client,
    _load_yaml,
    _transcribe_with_whisper,
    _evaluate_technical_answer,
)


# Simple bot avatar used when the interviewer is speaking
BOT_AVATAR_URL = "https://cdn-icons-png.flaticon.com/512/4712/4712105.png"


def _extract_first_code_block(text: str) -> str:
    """Return the first fenced code block (preferably python) from the text, if any."""
    if not text:
        return ""
    pattern = r"```(?:python)?\s*(.*?)```"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if not match:
        return ""
    return match.group(1).strip("\n")


def _tts_bytes(text: str) -> bytes:
    """Generate MP3 audio bytes from text using gTTS (for Streamlit playback)."""
    if not text:
        return b""
    buf = BytesIO()
    tts = gTTS(text=text, lang="en", slow=False)
    tts.write_to_fp(buf)
    buf.seek(0)
    return buf.read()


def _autoplay_audio(audio_bytes: bytes) -> None:
    """Autoplay audio in the browser without showing the default player chrome."""
    if not audio_bytes:
        return
    b64 = base64.b64encode(audio_bytes).decode("utf-8")
    html = f"""
    <audio autoplay style="display:none;">
        <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
        Your browser does not support the audio element.
    </audio>
    """
    st.markdown(html, unsafe_allow_html=True)


def _capture_mic_audio(key: str) -> bytes | None:
    """
    Record audio from the user's browser using streamlit-mic-recorder.
    Returns raw audio bytes (or None if nothing recorded yet).
    """
    audio = mic_recorder(
        start_prompt="🎙️ Start recording answer",
        stop_prompt="Stop recording",
        key=key,
    )
    if not audio or not audio.get("bytes"):
        return None
    return audio["bytes"]


def _transcribe_audio_bytes(audio_bytes: bytes) -> str:
    """Write audio bytes to a temp file and transcribe with Whisper."""
    tmp_dir = Path(tempfile.gettempdir())
    ts = int(time.time() * 1000)
    audio_path = tmp_dir / f"ctrl_hire_streamlit_answer_{ts}.wav"

    try:
        with audio_path.open("wb") as f:
            f.write(audio_bytes)
        return _transcribe_with_whisper(audio_path)
    except Exception as e:
        st.error(f"Audio transcription failed: {e}")
        return ""
    finally:
        try:
            if audio_path.exists():
                audio_path.unlink()
        except Exception:
            pass


def _init_streamlit_state() -> None:
    """Initialize / repair Streamlit session_state for an interview session."""
    # First-time initialization
    if "session_initialized" not in st.session_state:
        _ensure_sessions_dir()
        agents_cfg = _load_yaml(CONFIG_DIR / "agents.yaml")
        tasks_cfg = _load_yaml(CONFIG_DIR / "tasks.yaml")

        st.session_state.session_initialized = True
        st.session_state.candidate_profile: Dict[str, Any] = {}
        st.session_state.feedback_mode: str = "coaching"
        st.session_state.session_path: Path | None = None
        st.session_state.session_data: Dict[str, Any] = {}
        st.session_state.conversation_state: Dict[str, Any] = {"qa_list": []}
        st.session_state.latest_answer_text: str = ""
        st.session_state.interviewer_persona: str | None = None
        st.session_state.dynamic_system_prompt: str = _build_dynamic_interview_prompt(
            agents_cfg, tasks_cfg
        )
        st.session_state.coach_system_prompt: str = _build_coach_prompt(
            agents_cfg, tasks_cfg
        )
        st.session_state.openrouter_client = _get_openrouter_client()
        st.session_state.current_question_struct: Dict[str, Any] | None = None

    # Ensure newer keys exist even for older sessions
    if "phase" not in st.session_state:
        st.session_state.phase = "idle"
    if "current_round" not in st.session_state:
        st.session_state.current_round = None
    if "current_question_text" not in st.session_state:
        st.session_state.current_question_text = None
    if "current_end_interview" not in st.session_state:
        st.session_state.current_end_interview = False


def _start_new_session(
    user_name: str,
    target_role: str,
    experience_level: str,
    company_type: str,
    feedback_mode: str,
    job_description: str = "",
) -> None:
    """Create a new JSON session file and reset state."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in user_name)
    session_filename = f"{safe_name or 'candidate'}_{timestamp}.json"
    session_path = SESSIONS_DIR / session_filename

    candidate_profile = {
        "user_name": user_name,
        "target_role": target_role,
        "experience_level": experience_level,
        "company_type": company_type,
        # Optional free-text JD so the interviewer can specialize questions.
        "job_description": job_description.strip(),
    }

    session_data: Dict[str, Any] = {
        "candidate_profile": candidate_profile,
        "feedback_mode": feedback_mode,
        "qa_list": [],
        "interviewer_persona": None,
        "created_at_utc": timestamp,
    }

    with session_path.open("w", encoding="utf-8") as f:
        json.dump(session_data, f, ensure_ascii=False, indent=2)

    st.session_state.candidate_profile = candidate_profile
    st.session_state.feedback_mode = feedback_mode
    st.session_state.session_path = session_path
    st.session_state.session_data = session_data
    st.session_state.conversation_state = {"qa_list": []}
    st.session_state.latest_answer_text = ""
    st.session_state.interviewer_persona = None
    st.session_state.current_question_struct = None
    st.session_state.phase = "await_consent"
    st.session_state.current_round = None
    st.session_state.current_question_text = None
    st.session_state.current_end_interview = False
    st.session_state.answer_processed = False


def _append_qa_to_session(question_text: str, round_label: str, answer_text: str) -> None:
    """Append a Q&A pair to the JSON session file and update state."""
    if st.session_state.session_path is None:
        return

    qa_entry = {
        "turn": len(st.session_state.session_data.get("qa_list", [])) + 1,
        "round": round_label,
        "question": question_text,
        "answer_text": answer_text,
    }

    st.session_state.session_data.setdefault("qa_list", []).append(qa_entry)
    st.session_state.conversation_state["qa_list"] = st.session_state.session_data["qa_list"]

    with st.session_state.session_path.open("w", encoding="utf-8") as f:
        json.dump(st.session_state.session_data, f, ensure_ascii=False, indent=2)


def main() -> None:
    st.set_page_config(page_title="Ctrl+Hire", page_icon="🎧", layout="wide")

    _init_streamlit_state()

    # Global styling to give the app a more eye-catching, modern look.
    st.markdown(
        """
        <style>
        /* Overall app background */
        .stApp {
            background: radial-gradient(circle at top left, #020617 0, #020617 35%, #020617 40%, #020617 60%, #020617 100%);
            background-color: #020617;
        }

        /* Sidebar */
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #020617 0%, #111827 50%, #020617 100%);
            border-right: 1px solid rgba(148, 163, 184, 0.25);
        }

        /* Headings */
        h2, h3, h4 {
            color: #e5e7eb !important;
        }

        /* Cards / containers */
        .ctrlhire-card {
            background: radial-gradient(circle at top left, #4f46e5 0%, #0f172a 55%, #020617 100%);
            border-radius: 1.25rem;
            padding: 2rem 1.75rem;
            box-shadow: 0 24px 60px rgba(15, 23, 42, 0.85);
            border: 1px solid rgba(129, 140, 248, 0.45);
        }

        .ctrlhire-hero-title {
            font-size: 2.1rem;
            font-weight: 700;
            letter-spacing: 0.03em;
            color: #f9fafb;
            margin-bottom: 0.25rem;
        }

        .ctrlhire-hero-subtitle {
            color: #cbd5f5;
            font-size: 0.98rem;
            max-width: 46rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Sidebar navigation (single source of truth is 'nav_radio' in session_state)
    pages = ["🏠 Home", "🎙️ Interview", "🧠 Coach", "📊 Session log"]
    if "nav_radio" not in st.session_state:
        st.session_state.nav_radio = "🏠 Home"
    nav = st.sidebar.radio(
        "Navigation",
        pages,
        index=pages.index(st.session_state.nav_radio),
        key="nav_radio",
    )

    # --------------- HOME / SETUP PAGE -----------------
    if nav == "🏠 Home":
        # Hero section / landing feel
        st.markdown(
            """
            <div class="ctrlhire-card" style="margin-bottom: 1.75rem;">
              <div class="ctrlhire-hero-title">Ctrl+Hire</div>
              <p class="ctrlhire-hero-subtitle" style="margin-bottom: 0.85rem;">
                A modern, voice‑first studio to rehearse tough interviews with an AI that actually feels like the hiring panel.
              </p>
              <p class="ctrlhire-hero-subtitle" style="opacity: 0.9;">
                JD‑aware questions, built‑in code pads for DSA / SQL, and a performance coach that explains
                <strong>what you did well</strong> and <strong>what to sharpen next</strong> — all in one place.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("### Tell us about the interview you want to practice")
        col_left, col_right = st.columns(2)
        with col_left:
            user_name = st.text_input(
                "Your name",
                value="",
                placeholder="Enter your full name",
            )
            experience_level = st.selectbox(
                "Experience level",
                options=["Student / Fresher", "Junior", "Mid", "Senior"],
                index=1 if not st.session_state.candidate_profile.get("experience_level") else 1,
            )
        with col_right:
            target_role = st.text_input(
                "Target role",
                value=st.session_state.candidate_profile.get("target_role", ""),
                placeholder="e.g., SDE, Data Analyst, Product Manager",
            )
            company_type = st.text_input(
                "Company type",
                value=st.session_state.candidate_profile.get("company_type", ""),
                placeholder="e.g., Big Tech, startup, enterprise",
            )

        feedback_mode = st.radio(
            "Feedback style",
            options=["coaching", "strict"],
            horizontal=True,
            index=0 if st.session_state.feedback_mode == "coaching" else 1,
        )

        st.markdown("#### (Optional) Paste a specific job description")
        st.caption("Use this if you want a JD-focused interview that drills into core skills and day-to-day responsibilities.")
        job_description = st.text_area(
            "Job description text",
            value=st.session_state.candidate_profile.get("job_description", ""),
            placeholder="Paste the JD here so the interviewer can focus questions on its responsibilities, required skills, tools, and domains.",
            height=180,
            key="job_description_text",
        )

        col_btn_general, col_btn_jd = st.columns(2)
        with col_btn_general:
            start_general = st.button("Start general interview")
        with col_btn_jd:
            start_jd = st.button("Start JD-specific interview")

        if start_general:
            if not user_name.strip():
                st.warning("Please enter your name before starting the interview.")
                return
            _start_new_session(
                user_name=user_name.strip(),
                target_role=target_role.strip(),
                experience_level=experience_level.strip(),
                company_type=company_type.strip(),
                feedback_mode=feedback_mode,
                job_description="",
            )
            st.success("General interview session is ready. Go to the **Interview** tab in the sidebar when you're ready to start.")

        if start_jd:
            if not user_name.strip():
                st.warning("Please enter your name before starting the interview.")
                return
            _start_new_session(
                user_name=user_name.strip(),
                target_role=target_role.strip(),
                experience_level=experience_level.strip(),
                company_type=company_type.strip(),
                feedback_mode=feedback_mode,
                job_description=job_description.strip(),
            )
            st.success("JD-specific interview session is ready. Go to the **Interview** tab in the sidebar when you're ready to start.")

        return

    # For all other pages, require a session
    if st.session_state.session_path is None:
        st.info("No active session yet. Please configure your profile on the **Home** page first.")
        return

    # --------------- INTERVIEW PAGE -----------------
    if nav == "🎙️ Interview":
        st.markdown("### Interviewer")

        # Phase: interviewer introduction + asking for consent to start / continue
        if st.session_state.phase in ("await_consent", "await_next"):
            if st.session_state.phase == "await_consent":
                prompt_text = (
                    "Your interviewer is ready. When you're comfortable, click the button below to begin."
                )
            else:
                prompt_text = (
                    "When you're ready for the next question, click the button below."
                )
            st.markdown(f"**{prompt_text}**")

            label = (
                "I'm ready to start the interview"
                if not st.session_state.session_data.get("qa_list")
                else "I'm ready for the next question"
            )

            if st.button(label):
                client = st.session_state.openrouter_client
                question_struct = _ask_interviewer_question(
                    client=client,
                    system_prompt=st.session_state.dynamic_system_prompt,
                    model="meta-llama/llama-3.1-8b-instruct",
                    candidate_profile=st.session_state.candidate_profile,
                    conversation_state=st.session_state.conversation_state,
                    latest_answer=st.session_state.latest_answer_text,
                )

                st.session_state.current_question_struct = question_struct

                persona = question_struct.get("persona")
                first_turn = not st.session_state.session_data.get("qa_list")

                if persona and not st.session_state.interviewer_persona:
                    st.session_state.interviewer_persona = persona
                    st.session_state.session_data["interviewer_persona"] = persona
                    st.write(f"**Interviewer Persona:** {persona}")

                next_round = question_struct.get("next_round", "unknown")
                next_question_obj = question_struct.get("next_question", {}) or {}
                question_text = next_question_obj.get("text", "Please answer this question.")
                end_interview = bool(question_struct.get("end_interview", False))

                st.session_state.current_round = next_round
                st.session_state.current_question_text = question_text
                st.session_state.current_end_interview = end_interview
                st.session_state.phase = "await_answer"

                # Voice first, then show text + bot avatar.
                if first_turn and persona:
                    intro_and_question = (
                        f"Hello {st.session_state.candidate_profile.get('user_name') or 'there'}. "
                        f"I will be your interviewer for the {st.session_state.candidate_profile.get('target_role') or 'selected'} role. "
                        "Let's get started. "
                        + question_text
                    )
                    audio_bytes = _tts_bytes(intro_and_question)
                    _autoplay_audio(audio_bytes)
                else:
                    question_audio = _tts_bytes(question_text)
                    _autoplay_audio(question_audio)

                st.image(BOT_AVATAR_URL, width=96)
                st.markdown(f"**Question:** {question_text}")

        # Phase: waiting for the user's answer
        if nav == "🎙️ Interview" and st.session_state.phase == "await_answer" and st.session_state.current_question_text:
            question_struct = st.session_state.current_question_struct or {}
            next_q_meta = question_struct.get("next_question", {}) or {}
            question_type = str(next_q_meta.get("question_type", "") or "").lower()
            skill_tags = next_q_meta.get("skill_tags", []) or []
            technical_tags = {tag.lower() for tag in skill_tags}
            is_coding = any(
                tag in technical_tags for tag in ["dsa", "coding", "algorithm", "sql", "sql_query", "query"]
            ) or question_type in {"technical", "coding", "dsa", "sql"}

            if is_coding:
                # Show a simple "code space" only for coding questions
                st.subheader("Your Answer (code)")
                code_key = f"code_answer_{len(st.session_state.session_data.get('qa_list', [])) + 1}"
                starter_snippet = _extract_first_code_block(st.session_state.current_question_text or "")
                code_text = st.text_area(
                    "Write your solution here (complete the function stub shown in the question)",
                    value=starter_snippet,
                    height=220,
                    key=code_key,
                )

                if st.button("Submit code answer"):
                    answer_text = (code_text or "").strip()
                    if not answer_text:
                        st.warning("Please write some code before submitting.")
                        return

                    st.session_state.latest_answer_text = answer_text
                    _append_qa_to_session(
                        question_text=st.session_state.current_question_text,
                        round_label=st.session_state.current_round,
                        answer_text=answer_text,
                    )

                    tech_role_hint = f"{st.session_state.candidate_profile.get('target_role','')} @ {st.session_state.candidate_profile.get('company_type','')}"
                    tech_eval = _evaluate_technical_answer(
                        client=st.session_state.openrouter_client,
                        system_prompt_role=tech_role_hint,
                        model="meta-llama/llama-3.1-8b-instruct",
                        candidate_profile=st.session_state.candidate_profile,
                        question_text=st.session_state.current_question_text,
                        answer_text=answer_text,
                        question_type=question_type,
                        skill_tags=skill_tags,
                    )
                    if st.session_state.session_data.get("qa_list"):
                        st.session_state.session_data["qa_list"][-1]["technical_evaluation"] = tech_eval
                        if st.session_state.session_path is not None:
                            with st.session_state.session_path.open("w", encoding="utf-8") as f:
                                json.dump(
                                    st.session_state.session_data,
                                    f,
                                    ensure_ascii=False,
                                    indent=2,
                                )

                    verdict = tech_eval.get("short_verdict")
                    if verdict:
                        st.markdown(f"**Technical check:** {verdict}")

                    st.success("Code answer submitted.")
                    st.session_state.current_question_text = None

                    if st.session_state.current_end_interview:
                        st.session_state.phase = "finished"
                        st.info("Interviewer has concluded the interview. You can now request feedback below.")
                    else:
                        st.session_state.phase = "await_next"

                    st.rerun()
            else:
                st.subheader("Your Answer")

                # 1) Mic recorder: user can speak their answer in the browser.
                audio_bytes = _capture_mic_audio(
                    key=f"answer_mic_turn_{len(st.session_state.session_data.get('qa_list', [])) + 1}"
                )
                if audio_bytes:
                    answer_text = _transcribe_audio_bytes(audio_bytes).strip()
                    if answer_text:
                        st.session_state.latest_answer_text = answer_text
                        _append_qa_to_session(
                            question_text=st.session_state.current_question_text,
                            round_label=st.session_state.current_round,
                            answer_text=answer_text,
                        )
                        st.success("Answer submitted from your recording.")
                        st.session_state.current_question_text = None

                        if st.session_state.current_end_interview:
                            st.session_state.phase = "finished"
                            st.info("Interviewer has concluded the interview. You can now request feedback below.")
                        else:
                            st.session_state.phase = "await_next"

                        st.rerun()
                    else:
                        st.info("We couldn't understand the recording. You can try again or type your answer below.")

                # 2) Optional typed answer (fallback)
                typed_answer = st.text_area("Or type your answer here")

                if st.button("Submit typed answer", key="submit_typed_answer_interview"):
                    answer_text = (typed_answer or "").strip()
                    if not answer_text:
                        st.warning("Please type an answer before submitting.")
                        return

                    st.session_state.latest_answer_text = answer_text
                    _append_qa_to_session(
                        question_text=st.session_state.current_question_text,
                        round_label=st.session_state.current_round,
                        answer_text=answer_text,
                    )

                    st.success("Answer submitted.")
                    st.session_state.current_question_text = None

                    if st.session_state.current_end_interview:
                        st.session_state.phase = "finished"
                        st.info("Interviewer has concluded the interview. You can now request feedback below.")
                    else:
                        st.session_state.phase = "await_next"

    # --------------- COACH PAGE -----------------
    if nav == "🧠 Coach":
        st.subheader("Coach Feedback")
        qa_list = st.session_state.session_data.get("qa_list", [])
        if not qa_list:
            st.warning("No Q&A data available yet.")
        else:
            client = st.session_state.openrouter_client
            feedback = _analyze_with_coach(
                client=client,
                system_prompt=st.session_state.coach_system_prompt,
                model="meta-llama/llama-3.1-8b-instruct",
                candidate_profile=st.session_state.candidate_profile,
                qa_list=qa_list,
                feedback_mode=st.session_state.feedback_mode,
            )

            st.session_state.session_data["coach_feedback"] = feedback
            if st.session_state.session_path is not None:
                with st.session_state.session_path.open("w", encoding="utf-8") as f:
                    json.dump(st.session_state.session_data, f, ensure_ascii=False, indent=2)

            st.success("Coach feedback generated.")

            # Pretty presentation instead of raw JSON
            overall = feedback.get("overall_summary", "").strip()
            scores = feedback.get("dimension_scores", {}) or {}
            strengths = feedback.get("strengths", []) or []
            improvements = feedback.get("improvement_areas", []) or []
            per_round = feedback.get("per_round_feedback", {}) or {}
            inferred_skills = feedback.get("inferred_technical_skills", []) or []
            improved_answers = feedback.get("sample_improved_answers", []) or []

            if overall:
                st.markdown("#### Overall summary")
                st.write(overall)

            if scores:
                st.markdown("#### Scores (1–5)")
                cols = st.columns(len(scores))
                for (name, value), col in zip(scores.items(), cols):
                    with col:
                        col.metric(label=name.replace("_", " ").title(), value=str(value))

            col_left, col_right = st.columns(2)
            with col_left:
                if strengths:
                    st.markdown("#### Strengths")
                    for item in strengths:
                        st.markdown(f"- {item}")
            with col_right:
                if improvements:
                    st.markdown("#### Improvement areas")
                    for item in improvements:
                        st.markdown(f"- {item}")

            if inferred_skills:
                st.markdown("#### Inferred technical strengths")
                st.write(
                    "Based on your project and role-specific answers, the coach believes you show strength in:"
                )
                for skill in inferred_skills:
                    st.markdown(f"- {skill}")

            if improved_answers:
                st.markdown("#### Example improved answers for technical questions")
                for idx, item in enumerate(improved_answers, start=1):
                    question = item.get("question", "").strip()
                    improved = item.get("improved_answer", "").strip()
                    if not improved:
                        continue
                    st.markdown(f"**Problem {idx}:** {question}")
                    st.markdown(improved)

            if per_round:
                st.markdown("#### Round-by-round notes")
                for round_name, note in per_round.items():
                    if not note:
                        continue
                    st.markdown(f"**{round_name.replace('_', ' ').title()}**")
                    st.write(note)

        return

    # --------------- SESSION LOG PAGE -----------------
    if nav == "📊 Session log":
        st.markdown("### Session overview")
        qa_list = st.session_state.session_data.get("qa_list", [])
        if not qa_list:
            st.info("No questions have been asked yet in this session.")
        else:
            st.write(f"Total questions answered: **{len(qa_list)}**")
            st.table(
                [
                    {
                        "Turn": qa.get("turn"),
                        "Round": qa.get("round"),
                        "Question": qa.get("question"),
                    }
                    for qa in qa_list
                ]
            )

        if "coach_feedback" in st.session_state.session_data:
            st.markdown("### Last coach feedback (summary key)")
            fb = st.session_state.session_data["coach_feedback"]
            overall = (fb.get("overall_summary") or "").strip()
            if overall:
                st.write(overall)
        return


if __name__ == "__main__":
    main()



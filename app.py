"""Streamlit UI for the AI viral video pipeline.

This module only renders UI, wires up buttons, and holds session state.
All business logic lives in stages/ and services/.
"""

import os

import streamlit as st

# On Streamlit Community Cloud, secrets are configured in the dashboard and read via
# st.secrets. Bridge them into os.environ so config.py (plain env-var based) behaves
# identically locally (.env) and when deployed.
try:
    for _key, _value in st.secrets.items():
        if isinstance(_value, str):
            os.environ.setdefault(_key, _value)
except Exception:
    pass

from stages.audio import run_audio_stage
from stages.research import run_research_stage
from stages.review import approve_script, reject_script, validate_script
from stages.script import run_script_stage
from stages.video import run_video_stage
from config import get_settings
from state import PipelineState, PipelineStatus

st.set_page_config(page_title="AI Viral Video Generator", page_icon="🎬", layout="wide")

if "pipeline" not in st.session_state:
    st.session_state.pipeline = PipelineState()
state: PipelineState = st.session_state.pipeline


def run_stage_safely(stage_name: str, fn, *args) -> object | None:
    try:
        with st.spinner(f"{stage_name}..."):
            return fn(*args)
    except Exception as exc:
        state.record_error(stage_name, str(exc))
        st.error(f"{stage_name} failed: {exc}")
        return None


# --------------------------------------------------------------------------
# Sidebar
# --------------------------------------------------------------------------
with st.sidebar:
    st.header("Settings")

    try:
        settings = get_settings()
        settings_error = None
    except Exception as exc:
        settings = None
        settings_error = str(exc)

    st.subheader("API status")
    if settings_error:
        st.error(f"Configuration error: {settings_error}")
    else:
        st.success("OpenAI API key loaded")
        st.success("Composio API key loaded")
        st.success("Sarvam API key loaded")
        for label, value in [
            ("YouTube auth config", settings.youtube_auth_config_id),
            ("Twitter auth config", settings.twitter_auth_config_id),
            ("Exa auth config", settings.exa_auth_config_id),
            ("HeyGen auth config", settings.heygen_auth_config_id),
        ]:
            (st.success if value else st.warning)(
                f"{label}: {'configured' if value else 'using default connected account'}"
            )

        if settings.public_base_url:
            st.success(f"Public URL: {settings.public_base_url}")
        else:
            st.warning("PUBLIC_BASE_URL unset - audio works, video generation will fail")

    st.subheader("Provider")
    st.selectbox("LLM model", options=[settings.openai_model if settings else "gpt-4o"], disabled=True)

    if settings:
        with st.expander("Advanced"):
            st.text(f"Composio user: {settings.composio_user_id}")
            st.text(f"Sarvam voice: {settings.sarvam_speaker} ({settings.sarvam_model}, {settings.sarvam_language})")
            st.text(f"HeyGen avatar: {settings.heygen_avatar_id}")

# --------------------------------------------------------------------------
# Main page - topic input
# --------------------------------------------------------------------------
st.title("🎬 AI Viral Video Generator")

topic = st.text_input("Topic", value=state.topic or "Claude code for development in 2026")

if st.button("Generate", type="primary", disabled=settings_error is not None):
    state.topic = topic
    state.status = PipelineStatus.RESEARCHING
    research = run_stage_safely("Research", run_research_stage, topic)
    if research is not None:
        state.research = research
        state.status = PipelineStatus.SCRIPTING
        script = run_stage_safely("Script", run_script_stage, state)
        if script is not None:
            state.script = script
            state.approved = False
            state.status = PipelineStatus.AWAITING_REVIEW

# --------------------------------------------------------------------------
# Progress indicator
# --------------------------------------------------------------------------
def progress_glyph(done: bool, active: bool) -> str:
    if done:
        return "✓"
    if active:
        return "⏳"
    return "⬜"


st.markdown(
    " &nbsp;→&nbsp; ".join(
        [
            f"{progress_glyph(state.research is not None, state.status == PipelineStatus.RESEARCHING)} Research",
            f"{progress_glyph(state.script is not None, state.status == PipelineStatus.SCRIPTING)} Script",
            f"{progress_glyph(state.approved, state.status == PipelineStatus.AWAITING_REVIEW)} Review",
            f"{progress_glyph(state.audio_path is not None, state.status == PipelineStatus.GENERATING_AUDIO)} Voice",
            f"{progress_glyph(state.video_path is not None, state.status == PipelineStatus.GENERATING_VIDEO)} Video",
        ]
    )
)

if state.errors:
    with st.expander("Errors", expanded=True):
        for err in state.errors:
            st.error(err)

# --------------------------------------------------------------------------
# Research section
# --------------------------------------------------------------------------
if state.research:
    with st.expander("Research", expanded=False):
        st.markdown("**AI summary / news**")
        st.write(state.research.trends)

        st.markdown("**YouTube videos**")
        for video in state.research.videos:
            st.markdown(f"- [{video.title}]({video.url})")

        st.markdown("**Twitter/X insights**")
        for tweet in state.research.twitter_insights:
            st.markdown(f"- {tweet.text} ({tweet.likes} likes) - [link]({tweet.url})")

# --------------------------------------------------------------------------
# Script section
# --------------------------------------------------------------------------
if state.script is not None:
    st.subheader("Script")
    edited_script = st.text_area("Script text", value=state.script, height=200, key="script_editor")

    col1, col2, col3 = st.columns(3)

    with col1:
        feedback = st.text_input("Feedback for regeneration", value="Make the hook punchier")
        if st.button("Regenerate"):
            reject_script(state, feedback)
            state.status = PipelineStatus.SCRIPTING
            new_script = run_stage_safely("Script", run_script_stage, state)
            if new_script is not None:
                state.script = new_script
                state.status = PipelineStatus.AWAITING_REVIEW
                st.rerun()

    with col2:
        if st.button("Save"):
            state.script = edited_script
            st.success("Script saved.")

    with col3:
        if st.button("Approve", type="primary"):
            is_valid, error = validate_script(edited_script)
            if not is_valid:
                st.error(error)
            else:
                state.script = edited_script
                approve_script(state)
                st.success("Script approved!")

# --------------------------------------------------------------------------
# Audio section
# --------------------------------------------------------------------------
if state.approved:
    st.subheader("Audio")

    if st.button("Generate Voice"):
        state.status = PipelineStatus.GENERATING_AUDIO
        result = run_stage_safely("Audio", run_audio_stage, state.script)
        if result is not None:
            state.audio_url, state.audio_path = result
            state.status = PipelineStatus.AUDIO_READY

    if state.audio_path:
        st.audio(state.audio_path)
        with open(state.audio_path, "rb") as audio_file:
            st.download_button("Download audio", audio_file, file_name="speech.mp3")

# --------------------------------------------------------------------------
# Video section
# --------------------------------------------------------------------------
if state.audio_path:
    st.subheader("Video")

    if st.button("Generate Video"):
        state.status = PipelineStatus.GENERATING_VIDEO
        result = run_stage_safely("Video", run_video_stage, state.audio_url)
        if result is not None:
            _video_url, state.video_path = result
            state.status = PipelineStatus.DONE

    if state.video_path:
        st.video(state.video_path)
        with open(state.video_path, "rb") as video_file:
            st.download_button("Download video", video_file, file_name="final_video.mp4")

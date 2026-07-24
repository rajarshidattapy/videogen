"""Streamlit UI for the AI viral video pipeline.

This module only renders UI, wires up buttons, and holds session state.
All business logic lives in stages/ and client/.
"""

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

# Config precedence: .env (local) wins, then st.secrets (production) fills the rest.
#
# Loading .env into os.environ FIRST matters: the secrets bridge below uses
# setdefault, so anything .env already defined is left alone. Locally that means
# .env governs; on Streamlit Cloud there is no .env, so the dashboard secrets
# supply everything. Same code, two environments, no overrides fighting.
load_dotenv(Path(__file__).parent / ".env")  # explicit path - never cwd-dependent

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
from config import get_settings, reload_settings
from state import PipelineState, PipelineStatus

st.set_page_config(page_title="AI Viral Video Generator", page_icon="🎬", layout="wide")

if "pipeline" not in st.session_state:
    st.session_state.pipeline = PipelineState()
state: PipelineState = st.session_state.pipeline

try:
    settings = get_settings()
    settings_error = None
except Exception as exc:
    settings = None
    settings_error = str(exc)


def run_stage_safely(stage_name: str, fn, *args) -> object | None:
    try:
        with st.spinner(f"{stage_name}..."):
            return fn(*args)
    except Exception as exc:
        state.record_error(stage_name, str(exc))
        st.error(f"{stage_name} failed: {exc}")
        return None


@st.cache_data(ttl=300, show_spinner=False)
def check_composio() -> tuple[bool, str]:
    """Live credential check, cached for 5 minutes. Research and video both need this."""
    try:
        from client.composio_client import get_client

        client = get_client()
        accounts = client.connected_accounts.list(user_ids=[get_settings().composio_user_id])
        slugs = sorted({item.toolkit.slug.upper() for item in accounts.items})
        if not slugs:
            return False, "Key valid, but no toolkits connected for this user."
        return True, "Connected: " + ", ".join(slugs)
    except Exception as exc:
        message = str(exc)
        if "401" in message or "InvalidAPIKey" in message:
            return False, "Invalid COMPOSIO_API_KEY (401)."
        return False, f"{type(exc).__name__}: {message[:120]}"


def stage_header(number: int, title: str, done: bool, active: bool, blocked: str | None) -> None:
    if done:
        icon = "✅"
    elif active:
        icon = "⏳"
    elif blocked:
        icon = "🔒"
    else:
        icon = "⬜"
    st.markdown(f"#### {icon} {number}. {title}")
    if blocked and not done:
        st.caption(f"Blocked: {blocked}")


# --------------------------------------------------------------------------
# Composio status - needed by the pipeline blockers AND the settings view
# --------------------------------------------------------------------------
if settings_error:
    composio_ok, composio_msg = False, "Settings failed to load."
else:
    composio_ok, composio_msg = check_composio()

# Public deployment: no admin surface. Any visitor uses the pipeline on the owner's
# pre-configured keys; the Settings & connections panel is hidden entirely.
public_mode = bool(settings and settings.public_mode)
if public_mode:
    st.session_state.view = "studio"

if "view" not in st.session_state:
    st.session_state.view = "studio"

# --------------------------------------------------------------------------
# Sidebar - navigation only
# --------------------------------------------------------------------------
with st.sidebar:
    st.header("🎬 AI Video Studio")

    if not public_mode:
        if st.session_state.view == "studio":
            if st.button("⚙️ Settings & connections", use_container_width=True):
                st.session_state.view = "settings"
                st.rerun()
        else:
            if st.button("← Back to studio", use_container_width=True):
                st.session_state.view = "studio"
                st.rerun()

        if not composio_ok and st.session_state.view == "studio":
            st.warning("Composio not ready - open Settings.")

    if st.button("Reset pipeline", use_container_width=True):
        st.session_state.pipeline = PipelineState()
        st.session_state.pop("script_editor", None)
        st.rerun()

# --------------------------------------------------------------------------
# Settings view - service status + connections, on its own screen (hidden in public mode)
# --------------------------------------------------------------------------
if st.session_state.view == "settings" and not public_mode:
    st.title("⚙️ Settings & connections")

    st.subheader("Service status")
    if settings_error:
        st.error(f"Configuration error: {settings_error}")
    else:
        st.success("OpenAI - key loaded")
        st.success("Sarvam - key loaded")
        (st.success if composio_ok else st.error)(f"Composio (YouTube/Exa) - {composio_msg}")

        from client.reddit_client import reddit_available
        from client.twitter_client import twitter_available

        (st.success if twitter_available() else st.warning)(
            "Twitter/X (twscrape) - " + ("cookies set" if twitter_available() else "TWITTER_COOKIES unset - skipped")
        )
        (st.success if reddit_available() else st.warning)(
            "Reddit (PRAW) - " + ("credentials set" if reddit_available() else "REDDIT_CLIENT_ID/SECRET unset - skipped")
        )

        if settings.public_base_url:
            st.success(f"Public URL - {settings.public_base_url}")
        else:
            st.warning("PUBLIC_BASE_URL unset - video stage unavailable")

        if st.button("Re-check services", help="Re-reads .env and re-tests every credential"):
            reload_settings()
            check_composio.clear()
            st.rerun()

        with st.expander("Configuration"):
            st.text(f"OpenAI model:  {settings.openai_model}")
            st.text(f"Composio user: {settings.composio_user_id}")
            st.text(f"Sarvam voice:  {settings.sarvam_speaker}")
            st.text(f"Sarvam model:  {settings.sarvam_model} ({settings.sarvam_language})")
            st.text(f"HeyGen avatar: {settings.heygen_avatar_id}")

    st.divider()

    if settings_error:
        st.subheader("Connections")
        st.info("Fix the configuration error above to manage connections.")
    else:
        from client.connections import TOOLKITS, connected_slugs, start_connection

        try:
            connected = connected_slugs()
        except Exception:
            connected = set()

        st.subheader(f"Connections ({len(connected)}/{len(TOOLKITS)} connected)")
        st.caption(f"Connecting as Composio user `{settings.composio_user_id}`.")

        for toolkit in TOOLKITS:
            is_connected = toolkit.slug in connected
            st.markdown(f"**{'✅' if is_connected else '⬜'} {toolkit.label}** - {toolkit.hint}")

            if is_connected:
                continue

            api_key = client_id = client_secret = ""
            if toolkit.scheme == "api_key":
                api_key = st.text_input(
                    f"{toolkit.label} API key", type="password", key=f"key_{toolkit.slug}"
                )
            elif toolkit.scheme == "oauth_custom":
                col_id, col_secret = st.columns(2)
                client_id = col_id.text_input(f"{toolkit.label} client ID", key=f"cid_{toolkit.slug}")
                client_secret = col_secret.text_input(
                    f"{toolkit.label} client secret", type="password", key=f"sec_{toolkit.slug}"
                )

            if st.button(f"Connect {toolkit.label}", key=f"conn_{toolkit.slug}"):
                try:
                    url = start_connection(toolkit, api_key, client_id, client_secret)
                except Exception as exc:
                    st.error(f"{toolkit.label}: {exc}")
                else:
                    if url:
                        st.link_button(f"Authorize {toolkit.label}", url, type="primary")
                        st.caption("Authorize in the new tab, then press Re-check services.")
                    else:
                        st.success(f"{toolkit.label} connected.")
                        check_composio.clear()

            st.divider()

    st.stop()

# --------------------------------------------------------------------------
# Blockers, computed once and reused by each stage (studio view)
# --------------------------------------------------------------------------
# Research runs on any available source: Composio (YouTube/Exa), Twitter, or Reddit.
if settings_error:
    any_research_source = False
else:
    from client.reddit_client import reddit_available
    from client.twitter_client import twitter_available

    any_research_source = composio_ok or twitter_available() or reddit_available()

research_blocker = (
    None
    if any_research_source
    else "No research source - connect YouTube/Exa, or set Twitter/Reddit credentials (⚙️ Settings)."
)

video_blocker = None
if not composio_ok:
    video_blocker = composio_msg
elif settings and not settings.public_base_url:
    video_blocker = "PUBLIC_BASE_URL is unset - HeyGen cannot fetch audio from localhost."

st.title("🎬 AI Viral Video Generator")

st.markdown(
    " &nbsp;→&nbsp; ".join(
        [
            f"{'✅' if state.research else '⬜'} Research",
            f"{'✅' if state.script else '⬜'} Script",
            f"{'✅' if state.approved else '⬜'} Review",
            f"{'✅' if state.audio_path else '⬜'} Voice",
            f"{'✅' if state.video_path else '⬜'} Video",
        ]
    )
)

if state.errors:
    with st.expander(f"Errors ({len(state.errors)})", expanded=True):
        for err in state.errors:
            st.error(err)
        if st.button("Clear errors"):
            state.errors.clear()
            st.rerun()

# --------------------------------------------------------------------------
# 1. Research
# --------------------------------------------------------------------------
with st.container(border=True):
    stage_header(1, "Research", bool(state.research), state.status == PipelineStatus.RESEARCHING, research_blocker)
    st.caption("YouTube + Exa via Composio; Twitter/X via twscrape; Reddit via PRAW.")

    topic = st.text_input("Topic", value=state.topic or "Claude code for development in 2026")

    if st.button("Run research", type="primary", disabled=bool(research_blocker or settings_error)):
        state.topic = topic
        state.status = PipelineStatus.RESEARCHING
        research = run_stage_safely("Research", run_research_stage, topic)
        if research is not None:
            state.research = research
            state.status = PipelineStatus.RESEARCHED
        st.rerun()

    if research_blocker:
        if public_mode:
            st.info("Automated research is unavailable right now - write a script by hand in step 2.")
        else:
            st.info(
                "No research source yet - connect YouTube/Exa or set Twitter/Reddit credentials "
                "under ⚙️ Settings. You can still skip ahead and write a script by hand in step 2."
            )

    if state.research:
        st.markdown("**AI summary / news**")
        st.write(state.research.trends)

        if state.research.videos:
            st.markdown("**YouTube videos**")
            for video in state.research.videos:
                st.markdown(f"- [{video.title}]({video.url})")

        if state.research.twitter_insights:
            st.markdown("**Twitter/X insights**")
            for tweet in state.research.twitter_insights:
                st.markdown(f"- {tweet.text} ({tweet.likes} likes) - [link]({tweet.url})")

        if state.research.reddit_posts:
            st.markdown("**Reddit discussions**")
            for post in state.research.reddit_posts:
                st.markdown(f"- [{post.title}]({post.url}) ({post.score} pts, r/{post.subreddit})")

# --------------------------------------------------------------------------
# 2. Script
# --------------------------------------------------------------------------
with st.container(border=True):
    stage_header(2, "Script", state.script is not None, state.status == PipelineStatus.SCRIPTING, None)
    st.caption("Generated by OpenAI from the research, or written by hand.")

    col_gen, col_manual = st.columns(2)

    with col_gen:
        if st.button(
            "Generate from research",
            disabled=state.research is None or bool(settings_error),
            help=None if state.research else "Run research first",
        ):
            state.status = PipelineStatus.SCRIPTING
            script = run_stage_safely("Script", run_script_stage, state)
            if script is not None:
                state.script = script
                state.approved = False
                state.status = PipelineStatus.AWAITING_REVIEW
                # The editor is a keyed widget, so its old text survives a rerun.
                st.session_state.pop("script_editor", None)
            st.rerun()

    with col_manual:
        if st.button("Write manually", help="Skip research and paste your own script"):
            state.script = state.script or ""
            state.approved = False
            state.status = PipelineStatus.AWAITING_REVIEW
            st.rerun()

    if state.script is None:
        st.info("No script yet.")
    else:
        state.script = st.text_area("Script text", value=state.script, height=200, key="script_editor")
        st.caption(f"{len(state.script)} characters, ~{len(state.script.split())} words")

# --------------------------------------------------------------------------
# 3. Review
# --------------------------------------------------------------------------
with st.container(border=True):
    stage_header(
        3,
        "Review",
        state.approved,
        state.status == PipelineStatus.AWAITING_REVIEW,
        None if state.script is not None else "Needs a script.",
    )
    st.caption("Approve the script to unlock voice generation.")

    if state.script is None:
        st.info("Nothing to review yet.")
    else:
        feedback = st.text_input("Feedback for regeneration", value="Make the hook punchier")
        col_regen, col_approve = st.columns(2)

        with col_regen:
            if st.button(
                "Regenerate with feedback",
                disabled=state.research is None,
                help=None if state.research else "Regeneration needs research data",
            ):
                reject_script(state, feedback)
                state.status = PipelineStatus.SCRIPTING
                new_script = run_stage_safely("Script", run_script_stage, state)
                if new_script is not None:
                    state.script = new_script
                    state.status = PipelineStatus.AWAITING_REVIEW
                    st.session_state.pop("script_editor", None)
                st.rerun()

        with col_approve:
            if st.button("Approve", type="primary"):
                is_valid, error = validate_script(state.script)
                if not is_valid:
                    st.error(error)
                else:
                    approve_script(state)
                    st.rerun()

        if state.approved:
            st.success("Script approved.")

# --------------------------------------------------------------------------
# 4. Voice
# --------------------------------------------------------------------------
with st.container(border=True):
    stage_header(
        4,
        "Voice",
        state.audio_path is not None,
        state.status == PipelineStatus.GENERATING_AUDIO,
        None if state.approved else "Approve a script first.",
    )
    st.caption(
        f"Sarvam AI - {settings.sarvam_speaker} ({settings.sarvam_model})" if settings else "Sarvam AI"
    )

    if not state.approved:
        st.info("Approve a script to generate the voiceover.")
    else:
        if st.button("Generate voice", type="primary"):
            state.status = PipelineStatus.GENERATING_AUDIO
            result = run_stage_safely("Audio", run_audio_stage, state.script)
            if result is not None:
                state.audio_url, state.audio_path = result
                state.status = PipelineStatus.AUDIO_READY
            st.rerun()

    if state.audio_path:
        st.audio(state.audio_path)
        with open(state.audio_path, "rb") as audio_file:
            st.download_button("Download audio", audio_file, file_name="speech.mp3")
        if state.audio_url:
            st.caption(f"Public URL for HeyGen: {state.audio_url}")
        else:
            st.warning("Audio is local only - no PUBLIC_BASE_URL, so HeyGen cannot fetch it.")

# --------------------------------------------------------------------------
# 5. Video
# --------------------------------------------------------------------------
with st.container(border=True):
    max_attempts = settings.max_video_attempts if settings else 2
    attempts_left = max_attempts - state.video_attempts

    blocker = video_blocker or (None if state.audio_path else "Generate the voiceover first.")
    if attempts_left <= 0 and not blocker:
        blocker = f"Video attempt limit reached ({max_attempts}). Reset the pipeline to start over."

    stage_header(5, "Video", state.video_path is not None, state.status == PipelineStatus.GENERATING_VIDEO, blocker)
    st.caption("HeyGen avatar video. Only works on the deployed app.")

    if blocker:
        st.info(blocker)
    elif state.audio_path:
        st.caption(f"Attempts left: {attempts_left} of {max_attempts}")

    if st.button("Generate video", type="primary", disabled=bool(blocker)):
        state.video_attempts += 1
        state.status = PipelineStatus.GENERATING_VIDEO
        st.warning("HeyGen renders can take several minutes. Leave this tab open.")
        result = run_stage_safely("Video", run_video_stage, state.audio_url)
        if result is not None:
            _video_url, state.video_path = result
            state.status = PipelineStatus.DONE
        st.rerun()

    if state.video_path:
        st.video(state.video_path)
        with open(state.video_path, "rb") as video_file:
            st.download_button("Download video", video_file, file_name="final_video.mp4")

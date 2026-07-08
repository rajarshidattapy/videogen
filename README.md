
# AI Viral Video Generator

An AI agent that turns a topic into a ready-to-post short video: research →
script (with human review) → voiceover → avatar video.

This is the Python/Streamlit rewrite of the original TypeScript CLI (kept for
reference under `legacy/`). See `docs/python.md` for the migration PRD.

## Pipeline

```
Topic → Research (YouTube, Twitter/X, Exa) → Script → Human Review → Audio (ElevenLabs) → Video (HeyGen)
```

Research, ElevenLabs, and HeyGen access is brokered through
[Composio](https://composio.dev) - the same approach as the legacy CLI. YouTube,
Twitter/X, and Exa are called via per-user Composio MCP sessions exposed to an
OpenAI Agent; HeyGen is called directly through Composio's HTTP proxy.

## Project structure

```
app.py                  Streamlit UI - rendering, buttons, session state only
config.py               Environment/settings loading and validation
stages/                 Pipeline stage orchestration (no UI, no Streamlit imports)
  research.py
  script.py
  review.py
  audio.py
  video.py
services/                Vendor integrations
  composio_client.py     Composio singleton, MCP sessions, connected accounts
  openai_client.py       OpenAI Agents SDK helpers (build agent, run agent)
  elevenlabs_client.py   ElevenLabs speech generation
  heygen_client.py       HeyGen video generation, polling, download
state.py                 Pydantic models: ResearchData, PipelineState, ...
utils/                   Prompts, logging, small pure helpers
outputs/                 Generated audio/video (gitignored)
logs/                    App logs (gitignored)
```

## Setup

1. Create a virtual environment and install dependencies:

   ```bash
   python -m venv .venv
   source .venv/Scripts/activate   # Windows Git Bash; use .venv\Scripts\Activate.ps1 in PowerShell
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and fill in your API keys:

   ```bash
   cp .env.example .env
   ```

   You'll need an OpenAI API key, a Composio API key, and Composio auth configs
   for YouTube, Twitter/X, Exa, ElevenLabs, and HeyGen (connect each toolkit at
   https://platform.composio.dev, then paste the auth config IDs into `.env`).

3. Run the app:

   ```bash
   streamlit run app.py
   ```

## Deploying to Streamlit Community Cloud

1. Push this repo to GitHub, then create a new app at
   [share.streamlit.io](https://share.streamlit.io) pointing at `app.py`.

2. Python version: the repo pins `3.12` via `.python-version`. Community Cloud
   reads this automatically; no extra setting is needed.

3. Secrets: don't commit `.env`. Instead, open the app's **Settings → Secrets**
   in the Community Cloud dashboard and paste the same keys from
   `.env.example` in TOML form, e.g.:

   ```toml
   OPENAI_API_KEY = "sk-..."
   COMPOSIO_API_KEY = "..."
   COMPOSIO_USER_ID = "..."
   YOUTUBE_AUTH_CONFIG_ID = "..."
   TWITTER_AUTH_CONFIG_ID = "..."
   EXA_AUTH_CONFIG_ID = "..."
   ELEVENLABS_AUTH_CONFIG_ID = "..."
   HEYGEN_AUTH_CONFIG_ID = "..."
   ```

   `app.py` bridges `st.secrets` into environment variables on startup, so
   `config.py` picks them up exactly like a local `.env` file.

4. Storage is ephemeral: files written to `outputs/` and `logs/` survive for the
   life of the running container but are wiped on redeploy or reboot. That's
   fine for a single generate-review-download session; don't rely on it as
   permanent storage.

5. Video generation blocks the script run for the full HeyGen polling window
   (up to ~10 minutes by default). This is expected - the UI shows a spinner
   for the duration; it isn't a hang.

6. This app has no multi-tenant isolation: every visitor shares the same
   Composio user (and therefore the same connected YouTube/Twitter/ElevenLabs/
   HeyGen accounts). That's fine for a personal deployment; don't expose it
   publicly as a multi-user product without adding per-user auth.

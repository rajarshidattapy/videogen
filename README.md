
# AI Viral Video Generator

A Streamlit app that turns a topic into a ready-to-post short video: research →
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
agents/                 Pipeline stage orchestration (no UI, no Streamlit imports)
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
models/state.py          Pydantic models: ResearchData, PipelineState, ...
utils/                   Prompts, logging, small pure helpers
outputs/                 Generated audio/video (gitignored)
logs/                    App logs (gitignored)
tests/                   Unit tests for pure logic (helpers, models)
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

## Testing

```bash
pytest
```

Tests cover pure logic only (JSON extraction, prompt helpers, state models) -
the pipeline stages themselves call live external APIs and are not mocked.

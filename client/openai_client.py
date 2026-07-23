"""OpenAI Agents SDK helpers: building an Agent (optionally with Composio tools) and running it."""

from agents import Agent, Runner, set_default_openai_key

from config import get_settings

_configured_key: str | None = None


def _configure_key() -> None:
    """Hands the key to the Agents SDK, which reads os.environ and would otherwise
    miss a key that pydantic-settings loaded from .env into Settings only.

    Tracks the key itself rather than a done-flag, so reload_settings() picks up an
    edited .env instead of leaving the SDK on the key read at process start.
    """
    global _configured_key
    key = get_settings().openai_api_key
    if key != _configured_key:
        set_default_openai_key(key, use_for_tracing=True)
        _configured_key = key


def build_agent(name: str, instructions: str, tools=None) -> Agent:
    """Builds an Agent. `tools` is a Composio provider tool collection (from
    get_shared_tools()) or None for a tool-less agent like the scriptwriter."""
    settings = get_settings()
    _configure_key()
    return Agent(
        name=name,
        instructions=instructions,
        tools=list(tools) if tools else [],
        model=settings.openai_model,
    )


def run_agent(agent: Agent, prompt: str) -> str:
    """Runs the agent synchronously and returns its final text output.

    Raises RuntimeError if the agent produced no output at all.
    """
    result = Runner.run_sync(agent, prompt)
    if not result.final_output:
        raise RuntimeError(f"Agent '{agent.name}' produced no output.")
    return result.final_output

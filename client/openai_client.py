"""OpenAI Agents SDK helpers: building a hosted-MCP-backed Agent and running it."""

from agents import Agent, HostedMCPTool, Runner, set_default_openai_key

from config import get_settings
from client.composio_client import ToolkitSession

_key_configured = False


def _configure_key() -> None:
    """Hands the key to the Agents SDK, which reads os.environ and would otherwise
    miss a key that pydantic-settings loaded from .env into Settings only."""
    global _key_configured
    if not _key_configured:
        set_default_openai_key(get_settings().openai_api_key, use_for_tracing=True)
        _key_configured = True


def build_hosted_mcp_tool(session: ToolkitSession, server_label: str = "tool_router") -> HostedMCPTool:
    return HostedMCPTool(
        tool_config={
            "type": "mcp",
            "server_label": server_label,
            "server_url": session.url,
            "headers": session.headers,
            "require_approval": "never",
        }
    )


def build_agent(name: str, instructions: str, session: ToolkitSession | None = None) -> Agent:
    settings = get_settings()
    _configure_key()
    tools = [build_hosted_mcp_tool(session)] if session else []
    return Agent(name=name, instructions=instructions, tools=tools, model=settings.openai_model)


def run_agent(agent: Agent, prompt: str) -> str:
    """Runs the agent synchronously and returns its final text output.

    Raises RuntimeError if the agent produced no output at all.
    """
    result = Runner.run_sync(agent, prompt)
    if not result.final_output:
        raise RuntimeError(f"Agent '{agent.name}' produced no output.")
    return result.final_output

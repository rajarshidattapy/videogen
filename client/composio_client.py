"""Composio client + shared research session, wired for the OpenAI Agents SDK.

SDK: composio 0.18.0 with the composio-openai-agents provider. Per
https://docs.composio.dev/docs/quickstart the client is built with
OpenAIAgentsProvider and a tool-router session exposes ready-to-use Agent tools
via `session.tools()` - the Agents SDK executes those tools in-process (no hosted
MCP round-trip). HeyGen's connected-account lookup lives in heygen_client.py; this
module is only the client + the shared research session.
"""

from composio import Composio
from composio_openai_agents import OpenAIAgentsProvider

from config import get_settings

# The whole research pipeline runs on one session over these toolkits.
RESEARCH_TOOLKITS = ["youtube", "exa", "twitter"]

_client: Composio | None = None
_session = None  # ToolRouterSession, cached for the process
_tools = None  # provider-formatted tool collection from the shared session


def get_client() -> Composio:
    """Process-wide Composio client, built once with the OpenAI Agents provider."""
    global _client
    if _client is None:
        _client = Composio(
            api_key=get_settings().composio_api_key,
            provider=OpenAIAgentsProvider(),
        )
    return _client


def get_shared_tools():
    """Agent tools for youtube/exa/twitter from one shared session, memoized.

    One tool-router session already spans all three toolkits, so the research
    agents share it. The Composio user must have each toolkit connected (see
    client/connections.py).
    """
    global _session, _tools
    if _tools is None:
        _session = get_client().sessions.create(
            user_id=get_settings().composio_user_id,
            toolkits=RESEARCH_TOOLKITS,
        )
        _tools = _session.tools()
    return _tools


def reset_session_cache() -> None:
    """Drops the cached client + session so an edited .env / re-auth takes effect."""
    global _client, _session, _tools
    _client = None
    _session = None
    _tools = None

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
_tools_key: tuple[str, ...] | None = None  # toolkits the cached tools were built for


def get_client() -> Composio:
    """Process-wide Composio client, built once with the OpenAI Agents provider."""
    global _client
    if _client is None:
        _client = Composio(
            api_key=get_settings().composio_api_key,
            provider=OpenAIAgentsProvider(),
        )
    return _client


def connected_research_toolkits() -> list[str]:
    """Which of RESEARCH_TOOLKITS have an ACTIVE connection, in canonical order.

    sessions.create 400s if asked for a toolkit with no auth config, so the session
    must be built from only what's connected - research then runs on that subset.
    """
    accounts = get_client().connected_accounts.list(user_ids=[get_settings().composio_user_id])
    active = {a.toolkit.slug.lower() for a in accounts.items if str(a.status).upper() == "ACTIVE"}
    return [t for t in RESEARCH_TOOLKITS if t in active]


def get_shared_tools(toolkits: list[str]):
    """Agent tools for the given (connected) toolkits from one shared session.

    Memoized per toolkit set - if the connected set changes, the session rebuilds
    automatically, so newly-connected toolkits appear without a full reset.
    """
    global _session, _tools, _tools_key
    if not toolkits:
        raise RuntimeError(
            "No research toolkits connected - connect at least one of "
            "YouTube, Exa, or Twitter/X under Settings."
        )
    key = tuple(toolkits)
    if _tools is None or _tools_key != key:
        _session = get_client().sessions.create(
            user_id=get_settings().composio_user_id,
            toolkits=list(toolkits),
        )
        _tools = _session.tools()
        _tools_key = key
    return _tools


def reset_session_cache() -> None:
    """Drops the cached client + session so an edited .env / re-auth takes effect."""
    global _client, _session, _tools, _tools_key
    _client = None
    _session = None
    _tools = None
    _tools_key = None

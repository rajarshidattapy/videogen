from dataclasses import dataclass
from composio import Composio

from config import get_settings

RESEARCH_TOOLKITS = ["youtube", "exa", "twitter"]

_client: Composio | None = None
_session: "ToolkitSession | None" = None


@dataclass(slots=True)
class ToolkitSession:
    url: str
    headers: dict[str, str]


def get_client() -> Composio:
    global _client

    if _client is None:
        settings = get_settings()
        _client = Composio(
            api_key=settings.composio_api_key,
        )

    return _client


def get_shared_session() -> ToolkitSession:
    global _session

    if _session is not None:
        return _session

    settings = get_settings()

    session = get_client().sessions.create(
        user_id=settings.composio_user_id,
        toolkits=RESEARCH_TOOLKITS,
        mcp=True,
    )

    _session = ToolkitSession(
        url=session.mcp.url,
        headers=session.mcp.headers or {},
    )

    return _session


def reset_session_cache():
    global _client, _session
    _client = None
    _session = None
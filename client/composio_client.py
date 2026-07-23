"""Composio client singleton and toolkit-session / connected-account helpers.

Mirrors the legacy src/services/client.ts: every research/audio toolkit is used
through a per-user MCP session (composio.create(..., mcp=True)), while HeyGen is
driven directly through Composio's HTTP proxy against the caller's connected
account.
"""

from dataclasses import dataclass

from composio import Composio

from config import get_settings

_composio: Composio | None = None


def get_composio_client() -> Composio:
    global _composio
    if _composio is None:
        settings = get_settings()
        _composio = Composio(api_key=settings.composio_api_key)
    return _composio


@dataclass
class ToolkitSession:
    url: str
    headers: dict[str, str]


def create_toolkit_session(toolkits: list[str], auth_config_id: str | None = None) -> ToolkitSession:
    """Opens an MCP session scoped to the given toolkits for the configured Composio user."""
    settings = get_settings()
    composio = get_composio_client()

    auth_configs = {t: auth_config_id for t in toolkits} if auth_config_id else None

    session = composio.create(
        user_id=settings.composio_user_id,
        toolkits=toolkits,
        auth_configs=auth_configs,
        mcp=True,
    )
    return ToolkitSession(url=session.mcp.url, headers=session.mcp.headers or {})


def get_active_connection_id(toolkit_slug: str, auth_config_id: str | None = None) -> str:
    settings = get_settings()
    composio = get_composio_client()

    connections = composio.connected_accounts.list(
        user_ids=[settings.composio_user_id],
        statuses=["ACTIVE"],
    )

    for item in connections.items:
        if item.toolkit.slug.lower() == toolkit_slug.lower():
            if auth_config_id and item.auth_config.id != auth_config_id:
                continue
            return item.id

    raise RuntimeError(
        f"No active connection found for {toolkit_slug}. "
        f"Please authenticate User: {settings.composio_user_id}"
    )


def get_heygen_connection_id(toolkit_slug: str = "HEYGEN") -> str:
    settings = get_settings()
    composio = get_composio_client()

    connections = composio.connected_accounts.list(
        user_ids=[settings.composio_user_id],
        statuses=["ACTIVE"],
    )

    sorted_items = sorted(connections.items, key=lambda c: c.created_at, reverse=True)

    for item in sorted_items:
        if item.toolkit.slug.lower() == toolkit_slug.lower():
            return item.id

    raise RuntimeError(
        f"No active connection found for {toolkit_slug}. "
        f"Please authenticate User: {settings.composio_user_id}"
    )

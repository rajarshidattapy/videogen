"""Composio connection management, so toolkits can be connected from the app UI.

Composio only has managed OAuth credentials for YouTube on this plan. Twitter/X needs
your own OAuth app, and Exa/HeyGen authenticate with a plain API key.
"""

from dataclasses import dataclass

from client.composio_client import get_client
from config import get_settings


@dataclass(frozen=True)
class Toolkit:
    slug: str
    label: str
    scheme: str  # "oauth_managed" | "oauth_custom" | "api_key"
    hint: str


TOOLKITS = (
    Toolkit("youtube", "YouTube", "oauth_managed", "One click - Composio provides the OAuth app."),
    Toolkit("twitter", "Twitter/X", "oauth_custom", "Needs a client ID/secret from developer.x.com."),
    Toolkit("exa", "Exa", "api_key", "Paste your Exa API key from dashboard.exa.ai."),
    Toolkit("heygen", "HeyGen", "api_key", "Paste your HeyGen API key from app.heygen.com."),
)


def connected_slugs() -> set[str]:
    """Slugs with an ACTIVE connection for the configured Composio user."""
    client = get_client()
    accounts = client.connected_accounts.list(user_ids=[get_settings().composio_user_id])
    return {a.toolkit.slug.lower() for a in accounts.items if str(a.status).upper() == "ACTIVE"}


def _existing_auth_config(slug: str) -> str | None:
    client = get_client()
    for config in client.auth_configs.list().items:
        if config.toolkit.slug.lower() == slug.lower():
            return config.id
    return None


def ensure_auth_config(toolkit: Toolkit, client_id: str = "", client_secret: str = "") -> str:
    """Returns an auth config id for the toolkit, creating one if none exists."""
    existing = _existing_auth_config(toolkit.slug)
    if existing:
        return existing

    client = get_client()
    if toolkit.scheme == "oauth_managed":
        options = {"type": "use_composio_managed_auth"}
    elif toolkit.scheme == "oauth_custom":
        if not (client_id and client_secret):
            raise ValueError(f"{toolkit.label} needs an OAuth client ID and secret.")
        options = {
            "type": "use_custom_auth",
            "auth_scheme": "OAUTH2",
            "credentials": {"client_id": client_id, "client_secret": client_secret},
        }
    else:
        options = {"type": "use_custom_auth", "auth_scheme": "API_KEY", "credentials": {}}

    return client.auth_configs.create(toolkit=toolkit.slug, options=options).id


def start_connection(
    toolkit: Toolkit,
    api_key: str = "",
    client_id: str = "",
    client_secret: str = "",
) -> str | None:
    """Starts a connection and returns an OAuth URL to visit, or None if already active.

    API-key toolkits come back ACTIVE immediately. Note that Composio does not verify
    the key at this point, so a bad key fails later, when a tool is actually called.
    """
    if toolkit.scheme == "api_key" and not api_key:
        raise ValueError(f"{toolkit.label} needs an API key.")

    auth_config_id = ensure_auth_config(toolkit, client_id, client_secret)
    client = get_client()
    user_id = get_settings().composio_user_id

    # Composio-managed OAuth has to go through link(); initiate() was retired for it.
    if toolkit.scheme == "oauth_managed":
        return client.connected_accounts.link(user_id=user_id, auth_config_id=auth_config_id).redirect_url

    config = (
        {"auth_scheme": "API_KEY", "val": {"generic_api_key": api_key}}
        if toolkit.scheme == "api_key"
        else None
    )
    request = client.connected_accounts.initiate(
        user_id=user_id,
        auth_config_id=auth_config_id,
        config=config,
    )
    return request.redirect_url

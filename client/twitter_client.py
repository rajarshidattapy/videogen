"""Twitter/X search via twscrape - direct scraping on a cookie account.

Not Composio, not an LLM: twscrape hits X's search endpoints using a logged-in
account's cookies (auth_token + ct0), stored in a SQLite session db. Returns
structured tweets we map straight into TwitterInsight - no agent needed.
"""

import asyncio

from twscrape import API, gather

from config import get_settings
from state import TwitterInsight
from utils.logger import get_logger


def twitter_available() -> bool:
    """True when a cookie string is configured (no network check)."""
    return bool(get_settings().twitter_cookies.strip())


def _run(coro):
    # Streamlit runs sync with no event loop; asyncio.run makes a fresh one.
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


async def _search(query: str, limit: int) -> list:
    settings = get_settings()
    settings.ensure_output_dirs()
    api = API(str(settings.twscrape_db))
    # Cookie accounts with ct0 activate immediately. Re-adding an existing one
    # raises; ignore, the stored session is what we want.
    try:
        await api.pool.add_account_cookies("videogen", settings.twitter_cookies)
    except Exception:
        pass
    return await gather(api.search(query, limit=limit))


def search_tweets(query: str, limit: int = 20, top: int = 5) -> list[TwitterInsight]:
    """Searches recent tweets for `query`, returns the top `top` by likes."""
    if not twitter_available():
        return []

    try:
        tweets = _run(_search(query, limit))
    except Exception as exc:
        get_logger().warning("Twitter search failed: %s", exc)
        return []

    insights: list[TwitterInsight] = []
    for tweet in tweets:
        try:
            insights.append(
                TwitterInsight(
                    text=tweet.rawContent,
                    url=tweet.url,
                    likes=tweet.likeCount or 0,
                    comments=tweet.replyCount or 0,
                    views=tweet.viewCount or 0,
                )
            )
        except Exception:
            get_logger().warning("Skipping malformed tweet %s", getattr(tweet, "id", "?"))

    insights.sort(key=lambda i: i.likes, reverse=True)
    return insights[:top]

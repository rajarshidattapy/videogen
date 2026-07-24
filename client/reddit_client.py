"""Reddit search via PRAW (read-only) - direct API, not Composio, not an LLM.

Read-only needs only client_id/client_secret/user_agent (a script-type app on
reddit.com/prefs/apps). Searches r/all and maps submissions into RedditPost.
"""

import praw

from config import get_settings
from state import RedditPost
from utils.logger import get_logger


def reddit_available() -> bool:
    """True when client id + secret are configured (no network check)."""
    settings = get_settings()
    return bool(settings.reddit_client_id and settings.reddit_client_secret)


def _client() -> praw.Reddit:
    settings = get_settings()
    return praw.Reddit(
        client_id=settings.reddit_client_id,
        client_secret=settings.reddit_client_secret,
        user_agent=settings.reddit_user_agent,
        check_for_async=False,
    )


def search_posts(query: str, limit: int = 5) -> list[RedditPost]:
    """Searches r/all for `query`, most relevant first."""
    if not reddit_available():
        return []

    posts: list[RedditPost] = []
    try:
        results = _client().subreddit("all").search(
            query, sort="relevance", time_filter="year", limit=limit
        )
        for submission in results:
            posts.append(
                RedditPost(
                    title=submission.title,
                    url=f"https://reddit.com{submission.permalink}",
                    score=int(submission.score or 0),
                    comments=int(submission.num_comments or 0),
                    subreddit=str(submission.subreddit),
                )
            )
    except Exception as exc:
        get_logger().warning("Reddit search failed: %s", exc)

    return posts

"""Research stage: multi-platform content discovery.

YouTube + Exa go through Composio (LLM agents over a shared session); Twitter/X
and Reddit are scraped directly (twscrape / PRAW, no Composio, no LLM). Runs on
whatever subset of sources is available; at least one must be.

No UI logic - pure business logic, returning a ResearchData model.
"""

from state import RedditPost, ResearchData, TwitterInsight, VideoReference
from client.composio_client import connected_research_toolkits, get_shared_tools
from client.openai_client import build_agent, run_agent
from client.reddit_client import reddit_available, search_posts
from client.twitter_client import search_tweets, twitter_available
from utils.helpers import days_ago_iso, extract_json_array, extract_key_terms
from utils.logger import get_logger, stage
from utils.prompts import trend_researcher_instructions, youtube_scout_instructions


def _discover_youtube(tools, topic: str) -> list[VideoReference]:
    agent = build_agent("YouTube Scout", youtube_scout_instructions(topic), tools)

    raw_output = run_agent(agent, "Find top 5 viral shorts.")
    items = extract_json_array(raw_output)

    videos = []
    for item in items:
        try:
            videos.append(VideoReference(**item))
        except Exception:
            get_logger().warning("Skipping malformed YouTube item: %s", item)
    return videos


def _discover_trends(tools, topic: str) -> str:
    date_str = days_ago_iso(30)
    agent = build_agent("Trend Researcher", trend_researcher_instructions(topic, date_str), tools)

    raw_output = run_agent(agent, "Find fresh news.")
    return raw_output or "No trends found."


def run_research_stage(topic: str) -> ResearchData:
    """Runs research on whatever sources are available.

    YouTube/Exa need a Composio connection; Twitter needs TWITTER_COOKIES; Reddit
    needs REDDIT_CLIENT_ID/SECRET. At least one source must be usable - e.g. it
    works with just Twitter + Reddit and no Composio at all.
    """
    with stage("Research"):
        composio = connected_research_toolkits()  # subset of [youtube, exa]
        has_twitter, has_reddit = twitter_available(), reddit_available()

        sources = [*composio, *(["twitter"] if has_twitter else []), *(["reddit"] if has_reddit else [])]
        if not sources:
            raise ValueError(
                "No research source available. Connect YouTube/Exa under Settings, "
                "or set TWITTER_COOKIES / REDDIT_CLIENT_ID+SECRET."
            )
        get_logger().info("Research running with: %s", ", ".join(sources))

        videos: list[VideoReference] = []
        trends = "Trend research skipped (Exa not connected)."
        if composio:
            tools = get_shared_tools(composio)
            if "youtube" in composio:
                videos = _discover_youtube(tools, topic)
            if "exa" in composio:
                trends = _discover_trends(tools, topic)

        query = extract_key_terms(topic)
        twitter_insights: list[TwitterInsight] = search_tweets(query) if has_twitter else []
        reddit_posts: list[RedditPost] = search_posts(query) if has_reddit else []

        return ResearchData(
            videos=videos,
            raw_transcripts="Transcription disabled (Apify commented out).",
            trends=trends,
            twitter_insights=twitter_insights,
            reddit_posts=reddit_posts,
        )

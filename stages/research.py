"""Research stage: multi-platform content discovery (YouTube, Exa, Twitter/X).

No UI logic - pure business logic, returning a ResearchData model.
"""

from state import ResearchData, TwitterInsight, VideoReference
from client.composio_client import ToolkitSession, get_shared_session
from client.openai_client import build_agent, run_agent
from utils.helpers import days_ago_iso, extract_json_array, extract_key_terms
from utils.logger import get_logger, stage
from utils.prompts import (
    trend_researcher_instructions,
    twitter_scout_instructions,
    youtube_scout_instructions,
)


def _discover_youtube(session: ToolkitSession, topic: str) -> list[VideoReference]:
    agent = build_agent("YouTube Scout", youtube_scout_instructions(topic), session)

    raw_output = run_agent(agent, "Find top 5 viral shorts.")
    items = extract_json_array(raw_output)

    videos = []
    for item in items:
        try:
            videos.append(VideoReference(**item))
        except Exception:
            get_logger().warning("Skipping malformed YouTube item: %s", item)
    return videos


def _discover_trends(session: ToolkitSession, topic: str) -> str:
    date_str = days_ago_iso(30)
    agent = build_agent("Trend Researcher", trend_researcher_instructions(topic, date_str), session)

    raw_output = run_agent(agent, "Find fresh news.")
    return raw_output or "No trends found."


def _discover_twitter(session: ToolkitSession, topic: str) -> list[TwitterInsight]:
    search_query = extract_key_terms(topic)
    date_str = days_ago_iso(90)
    agent = build_agent("Twitter Scout", twitter_scout_instructions(search_query, date_str), session)

    raw_output = run_agent(agent, "Find viral threads.")
    items = extract_json_array(raw_output)

    insights = []
    for item in items:
        try:
            insights.append(TwitterInsight(**item))
        except Exception:
            get_logger().warning("Skipping malformed Twitter item: %s", item)
    return insights


def run_research_stage(topic: str) -> ResearchData:
    with stage("Research"):
        session = get_shared_session()
        videos = _discover_youtube(session, topic)
        trends = _discover_trends(session, topic)
        twitter_insights = _discover_twitter(session, topic)

        return ResearchData(
            videos=videos,
            raw_transcripts="Transcription disabled (Apify commented out).",
            trends=trends,
            twitter_insights=twitter_insights,
        )

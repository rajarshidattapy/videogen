"""Research stage: multi-platform content discovery (YouTube, Exa, Twitter/X).

No UI logic - pure business logic, returning a ResearchData model.
"""

from config import get_settings
from state import ResearchData, TwitterInsight, VideoReference
from services.composio_client import create_toolkit_session
from services.openai_client import build_agent, run_agent
from utils.helpers import days_ago_iso, extract_json_array, extract_key_terms
from utils.logger import get_logger, stage
from utils.prompts import (
    trend_researcher_instructions,
    twitter_scout_instructions,
    youtube_scout_instructions,
)


def _discover_youtube(topic: str) -> list[VideoReference]:
    settings = get_settings()
    session = create_toolkit_session(["youtube"], settings.youtube_auth_config_id)
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


def _discover_trends(topic: str) -> str:
    settings = get_settings()
    session = create_toolkit_session(["exa"], settings.exa_auth_config_id)
    date_str = days_ago_iso(30)
    agent = build_agent("Trend Researcher", trend_researcher_instructions(topic, date_str), session)

    raw_output = run_agent(agent, "Find fresh news.")
    return raw_output or "No trends found."


def _discover_twitter(topic: str) -> list[TwitterInsight]:
    settings = get_settings()
    session = create_toolkit_session(["twitter"], settings.twitter_auth_config_id)

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
        videos = _discover_youtube(topic)
        trends = _discover_trends(topic)
        twitter_insights = _discover_twitter(topic)

        return ResearchData(
            videos=videos,
            raw_transcripts="Transcription disabled (Apify commented out).",
            trends=trends,
            twitter_insights=twitter_insights,
        )

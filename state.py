"""Pydantic data models for research output and pipeline session state."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class VideoReference(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str
    url: str
    video_id: str = Field(validation_alias="videoId")
    view_count: str | None = Field(default=None, validation_alias="viewCount")


class TwitterInsight(BaseModel):
    text: str
    url: str
    likes: int
    comments: int
    views: int


class RedditPost(BaseModel):
    title: str
    url: str
    score: int
    comments: int
    subreddit: str = ""


class ResearchData(BaseModel):
    videos: list[VideoReference] = Field(default_factory=list)
    raw_transcripts: str = ""
    trends: str = ""
    twitter_insights: list[TwitterInsight] = Field(default_factory=list)
    reddit_posts: list[RedditPost] = Field(default_factory=list)


class PipelineStatus(StrEnum):
    IDLE = "idle"
    RESEARCHING = "researching"
    RESEARCHED = "researched"
    SCRIPTING = "scripting"
    AWAITING_REVIEW = "awaiting_review"
    GENERATING_AUDIO = "generating_audio"
    AUDIO_READY = "audio_ready"
    GENERATING_VIDEO = "generating_video"
    DONE = "done"
    ERROR = "error"


class PipelineState(BaseModel):
    topic: str = ""
    research: ResearchData | None = None
    script: str | None = None
    feedback: str | None = None
    approved: bool = False
    audio_url: str | None = None
    audio_path: str | None = None
    video_path: str | None = None
    status: PipelineStatus = PipelineStatus.IDLE
    errors: list[str] = Field(default_factory=list)

    def record_error(self, stage: str, message: str) -> None:
        self.status = PipelineStatus.ERROR
        self.errors.append(f"[{stage}] {message}")

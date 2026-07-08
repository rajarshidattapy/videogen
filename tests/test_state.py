from models.state import PipelineState, PipelineStatus, ResearchData, TwitterInsight, VideoReference


def test_video_reference_accepts_camel_case_llm_output():
    video = VideoReference(**{"title": "t", "url": "u", "videoId": "abc123", "viewCount": "1.2M"})
    assert video.video_id == "abc123"
    assert video.view_count == "1.2M"


def test_video_reference_view_count_optional():
    video = VideoReference(**{"title": "t", "url": "u", "videoId": "abc123"})
    assert video.view_count is None


def test_research_data_defaults_are_empty():
    research = ResearchData()
    assert research.videos == []
    assert research.twitter_insights == []
    assert research.trends == ""


def test_pipeline_state_starts_idle():
    state = PipelineState()
    assert state.status == PipelineStatus.IDLE
    assert state.errors == []


def test_pipeline_state_record_error_appends_and_sets_status():
    state = PipelineState()
    state.record_error("Research", "boom")
    assert state.status == PipelineStatus.ERROR
    assert state.errors == ["[Research] boom"]

    state.record_error("Script", "again")
    assert state.errors == ["[Research] boom", "[Script] again"]


def test_twitter_insight_roundtrip():
    tweet = TwitterInsight(text="hi", url="https://x.com/1", likes=10, comments=2, views=100)
    assert tweet.likes == 10

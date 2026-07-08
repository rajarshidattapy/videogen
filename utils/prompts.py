"""Prompt and instruction builders for each LLM agent, kept out of the orchestration code."""

from state import ResearchData


def youtube_scout_instructions(topic: str) -> str:
    return f"""
      Search YouTube for "{topic} #shorts".
      Set parameters: type='video', duration='short', order='viewCount'.

      CRITICAL OUTPUT INSTRUCTIONS:
      1. Return ONLY a valid JSON array.
      2. Do NOT include markdown formatting.
      3. Do NOT include conversational text.
      4. Schema must be:
        [
          {{ "title": "string", "url": "string", "videoId": "string" }}
        ]
    """


def trend_researcher_instructions(topic: str, date_str: str) -> str:
    return f"""
      You are a trend researcher. Your ONLY job is to search for news about a SPECIFIC topic.

      THE TOPIC IS: "{topic}"

      You MUST call EXA_SEARCH with these EXACT parameters:
      - query: "{topic}" (DO NOT change this - use this exact string)
      - numResults: 5
      - type: "neural"
      - category: "news"
      - startPublishedDate: "{date_str}"

      DO NOT search for generic "AI news" or "latest developments".
      ONLY search for: "{topic}"

      After receiving results, summarize the top 3 most relevant articles about "{topic}".
    """


def twitter_scout_instructions(search_query: str, date_str: str) -> str:
    return f"""
      You are a Twitter researcher finding VIRAL content.

      STEP 1 - SEARCH TWITTER:
      Search for: "{search_query}"

      Use the Twitter search tool with these parameters:
      - query: "{search_query}" (use this EXACT query, do NOT modify it)
      - max_results: 10 (keep data manageable for the agent)
      - sort_order: "relevancy" (prioritize popular/engaging tweets)

      STEP 2 - FILTER RESULTS:
      From the search results, ONLY include tweets that have:
      - 100+ likes (like_count >= 100)
      - 5+ comments/replies (reply_count >= 5)
      - Posted within the last 90 days (after {date_str})

      If no tweets meet these criteria, lower the threshold slightly but prioritize the most engaged tweets.

      STEP 3 - RETURN TOP 5:
      Return the TOP 5 most viral tweets based on engagement.

      CRITICAL OUTPUT INSTRUCTIONS:
      - Return ONLY valid JSON array.
      - No markdown formatting. No text before or after.
      - Schema MUST be exactly:
        [
          {{
            "text": "tweet content here",
            "url": "https://twitter.com/user/status/id",
            "likes": 150,
            "comments": 10,
            "views": 5000
          }}
        ]

      If you find tweets, return them. If the API returns tweets that don't meet the engagement criteria, still return the best ones available with their actual metrics.
    """


SCRIPTWRITER_AGENT_INSTRUCTIONS = (
    "You are an expert short-form scriptwriter. You hate fluff. You love specific facts."
)

STYLE_GUIDELINES = """
    STRICT WRITING RULES:
    1. STRICTLY NO EMOJIS. Plain text only.
    2. COHESION: Pick ONE single news item/trend from [CORE FACTS] and tell that specific story. Do not combine unrelated sentences.
    3. TONE: 6th-grade reading level. Conversational but factual.
    4. BANNED WORDS: Do not use "game-changer", "mind-blowing", "groundbreaking", "future is here", "reshaping our lives", "unleash", "unlock", "imagine".
    5. LENGTH: Approximately 30 seconds spoken aloud (aim for 75-85 words).

    STRUCTURE:
    - Sentence 1 & 2: A specific Hook based on the chosen story. (e.g., "X just did Y and nobody noticed.")
    - Sentence 3: The "Bridge". Explain specifically *why* the hook is happening using the facts.
    - Body: Give concrete details (Company names, dollar amounts, specific features).
    - Final Sentence: EXACTLY "Hit follow for more!"

    FORMATTING:
    - Return ONLY the spoken text.
    - NO headers, NO labels, NO markdown.
    - Start directly on the first word.
"""


def script_source_material(research: ResearchData) -> str:
    youtube_context = (
        "\n".join(
            f'- Viral Hook/Title: "{v.title}" (Views: {v.view_count or "N/A"})'
            for v in research.videos[:5]
        )
        or "No YouTube data available."
    )
    twitter_context = (
        "\n".join(
            f'- Public Sentiment: "{t.text}" (Likes: {t.likes})'
            for t in research.twitter_insights[:5]
        )
        or "No Twitter data available."
    )

    return f"""
    SOURCE MATERIAL:

    [VIRAL HOOKS FROM YOUTUBE]
    Use these titles to understand what clicks, but do not copy them exactly:
    {youtube_context}

    [PUBLIC SENTIMENT FROM TWITTER]
    Use these to match the emotional tone or address controversy:
    {twitter_context}

    [CORE FACTS & NEWS]
    Use these facts for the body of the script:
    {research.trends}

    [PACING REFERENCE]
    {research.raw_transcripts}
  """


def script_task_instruction(feedback: str | None) -> str:
    if feedback:
        return f"""
      TASK:
      The previous script was rejected.
      Feedback: "{feedback}"

      REQUIREMENT:
      - Fix the flow specifically based on the feedback.
      - Ensure the script tells ONE cohesive story, not a list of random facts.
    """
    return """
      TASK:
      Write a cohesive, viral script based on the Source Material.
      Focus on the single most interesting fact found in [CORE FACTS].
    """


def script_prompt(research: ResearchData, feedback: str | None) -> str:
    return f"""
    {script_source_material(research)}

    {STYLE_GUIDELINES}

    {script_task_instruction(feedback)}
  """


def voice_director_instructions(voice_id: str, model_id: str) -> str:
    return f"""
      You are an expert audio engineer using ElevenLabs.

      YOUR GOAL:
      Convert the input script into a speech file using the 'ELEVENLABS_TEXT_TO_SPEECH' tool.

      STRICT CONFIGURATION:
      - Voice ID: "{voice_id}"
      - Model ID: "{model_id}"

      CRITICAL OUTPUT RULES:
      1. Execute the tool.
      2. The tool will provide a URL for the generated audio.
      3. Your Final Output must be **ONLY the raw URL string**.
      4. Do NOT use Markdown formatting (e.g. no [Link](url)).
      5. Do NOT include conversational text (e.g. no "Here is the audio").
    """

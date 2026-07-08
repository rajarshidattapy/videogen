"""Script stage: prompt construction and LLM call to produce a viral short-form script.

No Streamlit code.
"""

from models.state import PipelineState
from services.openai_client import build_agent, run_agent
from utils.helpers import strip_code_block
from utils.logger import stage
from utils.prompts import SCRIPTWRITER_AGENT_INSTRUCTIONS, script_prompt


def run_script_stage(state: PipelineState) -> str:
    if not state.research:
        raise ValueError("Research data is missing!")

    with stage("Script"):
        agent = build_agent("Viral Scriptwriter", SCRIPTWRITER_AGENT_INSTRUCTIONS)
        raw_output = run_agent(agent, script_prompt(state.research, state.feedback))
        return strip_code_block(raw_output)

"""Human review: the script approval workflow.

Pure state transitions - Streamlit only wires buttons to these functions.
"""

from state import PipelineState, PipelineStatus


def validate_script(script: str | None) -> tuple[bool, str | None]:
    if not script or not script.strip() or script.startswith("Error:"):
        return False, "Script is empty or failed to generate."
    return True, None


def approve_script(state: PipelineState) -> PipelineState:
    state.approved = True
    state.feedback = None
    state.status = PipelineStatus.AWAITING_REVIEW
    return state


def reject_script(state: PipelineState, feedback: str) -> PipelineState:
    state.approved = False
    state.feedback = feedback
    return state

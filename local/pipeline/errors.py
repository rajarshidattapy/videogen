class PipelineError(RuntimeError):
    """A safe, actionable error that can be shown in the job status API."""


class ToolUnavailable(PipelineError):
    """A locally required executable, model checkout, or weight is unavailable."""


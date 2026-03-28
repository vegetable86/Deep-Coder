from dataclasses import dataclass, field


@dataclass
class ToolExecutionResult:
    name: str
    display_command: str
    model_output: str
    output_text: str
    diff_text: str | None = None
    reasoning_content: str | None = None
    metadata: dict = field(default_factory=dict)
    is_error: bool = False
    timeline_events: list[dict] = field(default_factory=list)


def build_model_error_payload(model_name: str, error, *, scope: str) -> dict:
    status_code = _extract_status_code(error)
    return {
        "scope": scope,
        "model_name": model_name,
        "message": str(error),
        "status_code": status_code,
        "retryable": _is_retryable_status(status_code),
        "error_type": error.__class__.__name__,
    }


def _extract_status_code(error) -> int | None:
    status_code = getattr(error, "status_code", None)
    if status_code is not None:
        return int(status_code)
    response = getattr(error, "response", None)
    response_status = getattr(response, "status_code", None)
    if response_status is not None:
        return int(response_status)
    return None


def _is_retryable_status(status_code: int | None) -> bool:
    if status_code is None:
        return False
    return status_code in {408, 409, 429} or status_code >= 500

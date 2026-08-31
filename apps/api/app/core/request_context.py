from contextvars import ContextVar

_request_id: ContextVar[str | None] = ContextVar("fintrace_request_id", default=None)


def set_request_id(value: str) -> None:
    _request_id.set(value)


def current_request_id() -> str | None:
    return _request_id.get()

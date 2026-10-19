import uuid
from contextvars import ContextVar

TRACE_ID = ContextVar("skillhub_trace_id", default=None)


class HubError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)


def require(condition, code="FORBIDDEN", message="当前操作未获授权", status=403):
    if not condition:
        raise HubError(code, message, status)


def missing():
    raise HubError("SKILL_NOT_FOUND_OR_NOT_ACCESSIBLE", "Skill 不存在或当前用户无权访问", 404)


def success(data, trace_id=None):
    return {"ok": True, "data": data, "trace_id": trace_id or TRACE_ID.get() or uuid.uuid4().hex}


def failure(error: HubError, trace_id=None):
    return {
        "ok": False,
        "error": {"code": error.code, "message": error.message, "retryable": error.status in {429, 503}},
        "trace_id": trace_id or TRACE_ID.get() or uuid.uuid4().hex,
    }

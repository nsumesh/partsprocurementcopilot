import json

from app.schemas.parts import FitmentResult, Part


def sse_part(index: int, part: Part, fitment: FitmentResult) -> str:
    payload = {
        "type": "part",
        "index": index,
        "part": part.model_dump(),
        "fitment": fitment.model_dump(),
    }
    return f"data: {json.dumps(payload)}\n\n"


def sse_clarify(question: str) -> str:
    payload = {"type": "clarify", "question": question}
    return f"data: {json.dumps(payload)}\n\n"


def sse_done() -> str:
    return f"data: {json.dumps({'type': 'done'})}\n\n"


def sse_error(message: str) -> str:
    payload = {"type": "error", "message": message}
    return f"data: {json.dumps(payload)}\n\n"

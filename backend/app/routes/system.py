"""System routes: health check and a quick "is the AI working?" ping."""

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool

from app.ai import llm
from app.auth.deps import signed_in
from app.config import settings
from app.db import User

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health():
    """Is the backend running? Also tells the UI which AI mode is set. Open to everyone (no sign-in)."""
    return {"status": "ok", "ai_mode": settings.ai_mode}


@router.get("/ai/ping")
async def ai_ping(user: User = Depends(signed_in)):
    """Ask the LLM to say namaste. Returns a friendly error if the LLM is not reachable."""
    info = llm.describe()
    messages = [{"role": "user", "content": "Say namaste in one word"}]
    try:
        # llm.chat is a normal (blocking) function; run it in a thread so the server stays responsive
        reply = await run_in_threadpool(llm.chat, messages, 32)
    except llm.LLMError as exc:
        return {"ok": False, "error": str(exc), **info}
    return {"ok": True, "reply": reply, **info}

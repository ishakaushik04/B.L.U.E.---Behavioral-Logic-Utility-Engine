"""
BLUE (Behavioral Logic & Utility Engine) - Backend
Principal Engineer build: FastAPI + Groq (LLM) + edge-tts (TTS)

Zero-cost stack:
  - STT is handled entirely client-side by the browser (Web Speech API), so
    no audio ever needs to be uploaded or transcribed server-side.
  - LLM inference runs on Groq's free tier (extremely low latency).
  - TTS runs on Microsoft's free edge-tts neural voice engine.

Run with:
    uvicorn main:app --reload
"""

import os
import uuid
import asyncio
import logging
from pathlib import Path
from collections import defaultdict
from typing import Dict, List

import edge_tts
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask
from pydantic import BaseModel

try:
    from groq import Groq
except ImportError:  # pragma: no cover
    Groq = None  # Allows the app to boot with a clear runtime error instead of an import crash

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("blue")

BASE_DIR = Path(__file__).resolve().parent
AUDIO_DIR = BASE_DIR / "audio_cache"
AUDIO_DIR.mkdir(exist_ok=True)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
TTS_VOICE = os.environ.get("BLUE_VOICE", "en-US-AriaNeural")
MAX_HISTORY_TURNS = 12  # user+assistant pairs kept per session, to bound token usage

SYSTEM_PROMPT = (
    "You are BLUE, a sharp, quick-witted, and fiercely loyal AI assistant. You read situations "
    "fast, get straight to the point, and have a confident, alert energy without ever being cold. "
    "Keep every response brief (1-3 sentences max) so it sounds natural when spoken aloud. NEVER "
    "use markdown, headers, bold text, bullet points, code blocks, or emojis. Write strictly in "
    "plain conversational prose suitable for text-to-speech engine playback."
)

groq_client = None
if GROQ_API_KEY and Groq is not None:
    groq_client = Groq(api_key=GROQ_API_KEY)
else:
    logger.warning(
        "GROQ_API_KEY is not set (or the groq package is missing). "
        "The /api/chat endpoint will return a clear error until this is fixed."
    )

# In-memory conversational state, keyed by session id.
# NOTE: this resets whenever the server restarts, and is per-process (fine for
# a single local user, which is the intended zero-cost deployment target).
chat_histories: Dict[str, List[dict]] = defaultdict(list)

# --------------------------------------------------------------------------
# App setup
# --------------------------------------------------------------------------

app = FastAPI(title="B.L.U.E. — Behavioral Logic & Utility Engine")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ChatResponse(BaseModel):
    text: str
    audio_url: str


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------

@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.post("/api/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest):
    user_message = (payload.message or "").strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    if groq_client is None:
        raise HTTPException(
            status_code=500,
            detail=(
                "GROQ_API_KEY is not configured on the server. "
                "Set it as an environment variable and restart the app."
            ),
        )

    session_id = payload.session_id or "default"
    history = chat_histories[session_id]

    # Build the message list: system prompt + trimmed history + new user turn
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history[-(MAX_HISTORY_TURNS * 2):])
    messages.append({"role": "user", "content": user_message})

    # --- 1. Call Groq for the text response -------------------------------
    try:
        completion = await asyncio.to_thread(
            groq_client.chat.completions.create,
            model=GROQ_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=200,
        )
        reply_text = completion.choices[0].message.content.strip()
    except Exception as exc:  # noqa: BLE001 - surface a clean error to the client
        logger.exception("Groq API call failed")
        raise HTTPException(status_code=502, detail=f"Groq API error: {exc}") from exc

    if not reply_text:
        reply_text = "My apologies, I seem to be at a loss for words at the moment."

    # Persist turn in session history
    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": reply_text})
    chat_histories[session_id] = history[-(MAX_HISTORY_TURNS * 2):]

    # --- 2. Synthesize speech with edge-tts --------------------------------
    filename = f"{uuid.uuid4().hex}.mp3"
    filepath = AUDIO_DIR / filename
    try:
        communicate = edge_tts.Communicate(text=reply_text, voice=TTS_VOICE)
        await communicate.save(str(filepath))
    except Exception as exc:  # noqa: BLE001
        logger.exception("edge-tts synthesis failed")
        # We still return the text even if audio synthesis fails, so the UI
        # can display it instead of hard-failing the whole interaction.
        return JSONResponse(
            status_code=200,
            content={
                "text": reply_text,
                "audio_url": "",
                "warning": f"Speech synthesis failed: {exc}",
            },
        )

    return {"text": reply_text, "audio_url": f"/api/audio/{filename}"}


@app.get("/api/audio/{filename}")
async def get_audio(filename: str):
    # Basic path traversal guard
    safe_name = Path(filename).name
    filepath = AUDIO_DIR / safe_name

    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Audio file not found or already consumed.")

    def _cleanup():
        try:
            filepath.unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            logger.warning("Failed to clean up audio file: %s", filepath)

    return FileResponse(
        path=filepath,
        media_type="audio/mpeg",
        filename=safe_name,
        background=BackgroundTask(_cleanup),
    )


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "groq_configured": groq_client is not None,
        "model": GROQ_MODEL,
        "voice": TTS_VOICE,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

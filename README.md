# B.L.U.E. (Behavioral Logic & Utility Engine) - Zero-Cost Voice Assistant

A browser-based voice assistant named after Blue, the sharp-eyed, fiercely
loyal velociraptor from Jurassic World: speech-to-text runs free and
instantly in your browser, the "brain" is Groq's free-tier LLM API, and the
voice is Microsoft's free `edge-tts` neural voice engine. Total running
cost: **$0**.

```
Browser mic → Web Speech API (STT, free, local)
      → FastAPI backend
            → Groq LLM (free tier, near-instant)
            → edge-tts (free neural voice synthesis)
      → Browser auto-plays the reply
```

---

## 1. Prerequisites

- Python 3.9+
- Google Chrome or Microsoft Edge (required — `webkitSpeechRecognition` is
  not supported in Firefox or Safari)
- A microphone
- A free Groq API key (see below)

---

## 2. Get a free Groq API key

1. Go to **https://console.groq.com** and sign up (free, no credit card required).
2. Once logged in, open the **API Keys** section in the left sidebar.
3. Click **Create API Key**, give it a name (e.g. `blue-local`), and copy
   the key immediately — Groq only shows it once.
4. Keep this key handy for step 4 below.

---

## 3. Project structure

Make sure your files are arranged like this:

```
blue/
├── main.py
├── requirements.txt
├── README.md
└── templates/
    └── index.html
```

(An `audio_cache/` folder is created automatically at runtime for temporary
MP3 files — you don't need to create it yourself.)

---

## 4. Install dependencies

It's recommended to use a virtual environment:

```bash
cd blue
python3 -m venv venv
source venv/bin/activate      # on Windows: venv\Scripts\activate

pip install -r requirements.txt
```

---

## 5. Set your Groq API key

Set it as an environment variable so the backend can read it.

**macOS / Linux:**
```bash
export GROQ_API_KEY="your_groq_api_key_here"
```

**Windows (PowerShell):**
```powershell
$env:GROQ_API_KEY="your_groq_api_key_here"
```

Optional overrides (defaults shown):

```bash
export GROQ_MODEL="llama-3.3-70b-versatile"   # or "openai/gpt-oss-120b"
export BLUE_VOICE="en-US-AriaNeural"          # any edge-tts voice name
```

If `GROQ_API_KEY` is not set, the app will still start and the interface
will load, but `/api/chat` will return a clear error message instead of
crashing — so you'll know immediately what to fix.

---

## 6. Run the application

```bash
uvicorn main:app --reload
```

Then open your browser to:

```
http://127.0.0.1:8000
```

You should see the glowing Blue core interface.

---

## 7. Using Blue

1. Click the glowing core (the mic button) — your browser will ask for
   microphone permission the first time. Allow it.
2. The ring turns **cyan and pulses** while listening.
3. Speak your message, then pause — the browser automatically stops
   listening (this is native `webkitSpeechRecognition` behavior).
4. The ring turns **amber** while Blue thinks (Groq is generating a reply).
5. The ring turns **green** and Blue's voice plays automatically while
   speaking the response.
6. The conversation log below the core keeps a running transcript for the
   session.

Conversation memory persists for the browser session (stored via a session
ID in `localStorage`) and is kept in server memory — it resets if you
restart the backend.

---

## 8. Troubleshooting

| Problem | Likely cause / fix |
|---|---|
| "Speech recognition unsupported" banner | You're using Firefox/Safari. Switch to Chrome or Edge. |
| "Microphone access was denied" | Click the padlock icon in your browser's address bar and allow microphone access, then reload. |
| `/api/chat` returns "GROQ_API_KEY is not configured" | You forgot to export `GROQ_API_KEY` before running `uvicorn`, or you're running in a new terminal tab where the variable isn't set. |
| Groq API error mentioning rate limits | You've hit the free tier's rate limit — wait a minute and try again, or reduce request frequency. |
| No audio plays but text appears | Some browsers block autoplay until you interact with the page first — click anywhere on the page once, then try again. Check `server.log`/console for `edge-tts` errors (e.g. no internet access, since `edge-tts` requires an internet connection to Microsoft's endpoint). |
| Port already in use | Run on a different port: `uvicorn main:app --port 8001 --reload` |

---

## 9. Notes on the "zero-cost" architecture

- **STT** costs nothing because it never leaves your browser — no audio is
  uploaded anywhere.
- **LLM** calls use Groq's free developer tier, which offers generous rate
  limits for personal projects at no cost.
- **TTS** uses `edge-tts`, an open-source library that calls Microsoft
  Edge's public neural voice service for free (no API key required).
- The backend is a single lightweight FastAPI process — it can run on your
  laptop, or be deployed for free on services like Render, Railway, or
  Fly.io's free tiers.

Enjoy your new assistant — sharp, quick, and always on your side.

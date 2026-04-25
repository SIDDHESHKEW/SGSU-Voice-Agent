import logging
from typing import Optional

import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Basic console logging setup.
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("ai-counsellor-backend")

app = FastAPI(title="AI University Counsellor API")

# Enable CORS for all origins (frontend can call from anywhere).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


def get_fallback_response(message: str) -> str:
    """Return short, friendly fallback responses in Hindi + English mix."""
    try:
        msg = (message or "").lower()

        if "course" in msg or "program" in msg or "cse" in msg or "aiml" in msg:
            return (
                "Sure! Humare popular programs hain: B.Tech CSE, B.Tech AIML, Data Science, "
                "and Business. Aap interest batao, main best option suggest kar dunga."
            )

        if "admission" in msg or "apply" in msg or "eligibility" in msg:
            return (
                "Admission simple hai: online form fill karo, documents upload karo, aur counselling complete karo. "
                "Need ho to main step-by-step guide de sakta hoon."
            )

        if "fee" in msg or "fees" in msg or "cost" in msg:
            return (
                "Sample fee idea: B.Tech around 1.2L-1.8L per year (program-wise vary karta hai). "
                "Exact fees ke liye official admission desk se latest structure verify karo."
            )

        return (
            "Welcome! Main university counsellor assistant hoon. Aap courses, admission, fees, "
            "ya campus info pooch sakte ho."
        )
    except Exception as ex:
        logger.exception("Fallback response failed: %s", ex)
        return "Sorry, abhi issue aa gaya. Please thodi der baad dobara try karo."


def _call_gemini(message: str) -> Optional[str]:
    """Call Gemini API and return text response, or None if unavailable."""
    try:
        api_key = "YOUR_GEMINI_API_KEY"
        if not api_key or api_key == "YOUR_GEMINI_API_KEY":
            logger.warning("Gemini API key is placeholder. Using fallback response.")
            return None

        endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/"
            "models/gemini-2.5-flash:generateContent"
        )

        prompt = (
            "You are a friendly university counsellor. "
            "Keep answer short, warm, and student-friendly. "
            "Use simple Hindi + English mix naturally. "
            f"Student message: {message}"
        )

        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.6,
                "maxOutputTokens": 120,
            },
        }

        logger.info("Calling Gemini API...")
        response = requests.post(
            endpoint,
            params={"key": api_key},
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=15,
        )

        if response.status_code != 200:
            logger.error("Gemini API failed: status=%s body=%s", response.status_code, response.text[:300])
            return None

        data = response.json()
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        text = " ".join([p.get("text", "") for p in parts]).strip()

        if not text:
            logger.warning("Gemini response was empty.")
            return None

        # Keep response short and clean.
        return text[:320]
    except Exception as ex:
        logger.exception("Gemini call error: %s", ex)
        return None


def get_ai_response(message: str) -> str:
    """Gemini-first response with fallback logic."""
    try:
        ai_reply = _call_gemini(message)
        if ai_reply:
            logger.info("AI response generated from Gemini.")
            return ai_reply

        logger.info("Using fallback response logic.")
        return get_fallback_response(message)
    except Exception as ex:
        logger.exception("get_ai_response failed: %s", ex)
        return "Sorry, system busy hai. Please ek baar phir try karo."


@app.get("/")
def health_check() -> dict:
    try:
        return {"status": "ok", "message": "AI Counsellor backend running"}
    except Exception as ex:
        logger.exception("Health check failed: %s", ex)
        return {"status": "error"}


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    try:
        user_message = (payload.message or "").strip()
        logger.info("Incoming /chat message: %s", user_message)

        if not user_message:
            return ChatResponse(reply="Please message type karo, phir main help karta hoon.")

        reply = get_ai_response(user_message)
        logger.info("Outgoing /chat reply: %s", reply)
        return ChatResponse(reply=reply)
    except Exception as ex:
        logger.exception("/chat endpoint failed: %s", ex)
        return ChatResponse(reply="Sorry, kuch error aa gaya. Please dobara try karo.")


if __name__ == "__main__":
    try:
        import uvicorn

        logger.info("Starting FastAPI server on port 8000...")
        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
    except Exception as ex:
        logger.exception("Server start failed: %s", ex)

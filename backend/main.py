import logging
import os
from typing import Optional

import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Basic console logging setup.
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("ai-counsellor-backend")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

SYSTEM_PROMPT = """You are an AI counsellor for Scope Global Skills University (SGSU), Bhopal, Madhya Pradesh, India.

ABOUT UNIVERSITY:
Scope Global Skills University (SGSU) is a private university established in 2023 by the Madhya Pradesh Assembly. It is a skill-focused university aligned with NEP (National Education Policy) and NSQF framework. The university focuses on industry-oriented, practical education with strong placement support.

RECOGNITION & FEATURES:

* Recognized by UGC
* Approved by AICTE
* Associated with AIU
* Industry collaborations (NASSCOM, ASDC, etc.)
* Focus on skill-based learning + real-world training
* Offers placement assistance and career support

LOCATION:

* Bhopal, Madhya Pradesh, India

COURSES OFFERED:

UNDERGRADUATE (UG):

* B.Tech (CSE, AI/ML, Data Science, etc.)
* BBA (Business, Hospitality, Management)
* BCA (Cyber Security, Computer Applications)
* B.Sc (Science streams like Physics, Chemistry, Biology, etc.)
* B.Com (Commerce, Accounts, Retail Management)
* BA (Arts)
* B.Voc and other skill-based programs

POSTGRADUATE (PG):

* M.Tech
* MBA
* MCA
* M.Sc
* M.Com
* MA
* M.Voc

DIPLOMA PROGRAMS:

* Engineering Diplomas
* Safety & Fire Engineering
* Industrial Safety
* Language Diplomas (French, German, Japanese)
* Various skill-based diplomas

COURSE DURATION:

* UG courses: 3-4 years
* PG courses: 2 years
* Diploma: 1-3 years

FEES STRUCTURE (APPROX):

* B.Tech: Rs1.6L - Rs3.2L total
* B.Sc / B.Com / BBA: Rs40K - Rs6L depending on course
* PG courses: Rs20K - Rs1.5L approx
* Diploma: Rs10K - Rs35K approx

ADMISSION PROCESS:

* Admission is merit-based (no entrance exam required)
* Based on Class 12 marks (for UG)
* Based on graduation marks (for PG)
* Students must apply online through official website
* Direct admission available

ELIGIBILITY:

* UG: 10+2 (45%-80% depending on course)
* PG: Graduation with ~50% marks

SPECIAL FEATURES:

* Work Integrated Learning Programs (WILP)
* Industry-linked curriculum
* Hands-on practical training
* Skill development focus
* Career-oriented education

PLACEMENTS:

* Placement assistance provided
* Industry partnerships for training and hiring

TONE:

* Friendly, helpful counsellor
* Hinglish allowed
* Short and clear answers

SCRIPT RULE:
Write Hindi words only in Devanagari script and English words only in English script.
Do not write Hindi words in English letters.
"""

HINDI_HINTS = [
    "kya",
    "kaise",
    "mujhe",
    "aap",
    "hai",
    "nahi",
    "karun",
    "admission",
    "fees",
    "hindi",
]

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
                "SGSU में लोकप्रिय programs हैं: B.Tech CSE, B.Tech AI/ML, Data Science, BBA, BCA और अन्य skill-based programs. "
                "आप अपनी रुचि बताइए, मैं best option suggest कर दूंगा।"
            )

        if "admission" in msg or "apply" in msg or "eligibility" in msg:
            return (
                "Admission merit-based है और entrance exam आवश्यक नहीं है। "
                "आप official website पर online apply करें, documents upload करें, फिर counselling process complete करें।"
            )

        if "fee" in msg or "fees" in msg or "cost" in msg:
            return (
                "Approx fees: B.Tech Rs1.6L-Rs3.2L total, UG programs Rs40K-Rs6L, PG Rs20K-Rs1.5L, Diploma Rs10K-Rs35K. "
                "Exact fees course-wise admission desk से verify करें।"
            )

        if "hindi" in msg:
            return "बिलकुल, मैं Hindi और English दोनों समझता हूं। आप अपना सवाल पूछिए।"

        if "who are you" in msg or "tum kaun" in msg:
            return "मैं SGSU का AI university counsellor assistant हूं। मैं admission, courses, fees और eligibility में आपकी मदद करता हूं।"

        return (
            "नमस्ते! मैं SGSU counsellor assistant हूं। आप courses, admission, fees, eligibility और campus location के बारे में पूछ सकते हैं।"
        )
    except Exception as ex:
        logger.exception("Fallback response failed: %s", ex)
        return "Sorry, abhi issue aa gaya. Please thodi der baad dobara try karo."


def _call_gemini(full_prompt: str) -> Optional[str]:
    """Call Gemini API and return text response, or None if unavailable."""
    try:
        api_key = GEMINI_API_KEY
        if not api_key:
            logger.warning("Gemini API key is missing. Set GEMINI_API_KEY env var. Using fallback response.")
            return None

        endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/"
            "models/gemini-2.5-flash:generateContent"
        )

        lowered = (full_prompt or "").lower()
        has_hindi_signal = any(token in lowered for token in HINDI_HINTS)
        response_style = (
            "Reply in simple Hindi-English mix (Hinglish), but Hindi must be in Devanagari and English in English script."
            if has_hindi_signal
            else "Reply in clear English unless user asks for Hindi."
        )

        prompt = (
            "You are SGSU University AI Counsellor. "
            "Be accurate, warm, and practical for student guidance. "
            f"{response_style} "
            "Give 1-3 short sentences, but do not answer with only greeting words. "
            "If user asks about admission/courses/fees, provide concrete next steps. "
            f"{full_prompt}"
        )

        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.35,
                "topP": 0.9,
                "maxOutputTokens": 220,
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
            if response.status_code == 403 and "leaked" in response.text.lower():
                logger.error("Gemini rejected this key as leaked/blocked. Generate a new key and update GEMINI_API_KEY.")
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
        full_prompt = SYSTEM_PROMPT + "\nUser: " + message + "\nCounsellor:"
        ai_reply = _call_gemini(full_prompt)
        if ai_reply:
            low_quality_tokens = {"hi", "hi there", "hello", "haan bilkul", "bilkul", "great"}
            cleaned = ai_reply.strip().lower()
            short_reply = len(cleaned.split()) <= 2
            generic_reply = cleaned in low_quality_tokens
            if short_reply or generic_reply:
                logger.warning("Gemini reply too short/generic, switching to fallback for better quality.")
                return get_fallback_response(message)

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
        print("User:", user_message)

        if not user_message:
            reply = "कृपया अपना संदेश लिखें, फिर मैं मदद करता हूं।"
            print("AI:", reply)
            return ChatResponse(reply=reply)

        reply = get_ai_response(user_message)
        logger.info("Outgoing /chat reply: %s", reply)
        print("AI:", reply)
        return ChatResponse(reply=reply)
    except Exception as ex:
        logger.exception("/chat endpoint failed: %s", ex)
        reply = "क्षमा करें, कुछ त्रुटि आ गई। कृपया दोबारा प्रयास करें।"
        print("AI:", reply)
        return ChatResponse(reply=reply)


if __name__ == "__main__":
    try:
        import uvicorn

        logger.info("Starting FastAPI server on port 8000...")
        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
    except Exception as ex:
        logger.exception("Server start failed: %s", ex)

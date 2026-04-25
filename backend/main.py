import logging
import os
import random
import re
import sqlite3
from typing import Optional

import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("ai-counsellor-backend")

HUGGINGFACE_MODEL_URL = "https://router.huggingface.co/v1/chat/completions"
HUGGINGFACE_MODEL_NAME = "katanemo/Arch-Router-1.5B:hf-inference"
DB_PATH = os.path.join(os.path.dirname(__file__), "chat_cache.db")
ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")

SGSU_CONTEXT = """Scope Global Skills University (SGSU), Bhopal, Madhya Pradesh, India.
Established in 2023 by the Madhya Pradesh Assembly.
Skill-focused private university aligned with NEP and NSQF framework.
Recognized by UGC, approved by AICTE, associated with AIU.
Focus on industry-oriented, practical education with placement support.

Campus and contact:
SCOPE Campus, NH-12, Near Misrod, Hoshangabad Road, Bhopal.
Phone: +91-7552432903/904
Fax: +91-7552432909
Email: info@sgsuniversity.ac.in

Leadership and administration:
Chancellor: Dr. Siddharth Chaturvedi.
Pro-Chancellor: Abhishek Pandit.
Vice Chancellor references on official SGSU pages include Dr. Ajay Bhushan.
A January 10, 2025 official SGSU news post names Dr. Vijay Singh as Vice-Chancellor.
Registrar references on official SGSU pages include Dr. Sitesh Sinha / Dr Sitesh Sinha.

Academic areas and faculties listed on official SGSU pages:
Engineering & Technology Skills
Management Studies
Future Skills
Banking Finance & Commerce
Information Technology
Emerging Technologies
Education & Training
Humanities & Liberal Arts
Science
Agriculture & Allied Technologies

Programs:
UG: B.Tech, BBA, BCA, B.Sc, B.Com, BA, B.Voc
PG: M.Tech, MBA, MCA, M.Sc, M.Com, MA, M.Voc
Diploma programs also available.

Admission:
Admission is merit-based.
No entrance exam required.
UG admissions are based on Class 12 marks.
PG admissions are based on graduation marks.
Students can apply online through the official website.
Direct admission available.

Fees:
Approx fee range starts around 40K and can go up to around 3.2 lakh depending on course.

Vision and mission:
Trusted university in skill-based education.
Industry-linked curriculum, practical training, and employability focus."""

SYSTEM_PROMPT = (
    "You are an official AI counsellor of Scope Global Skills University (SGSU).\n"
    "Use ONLY the provided SGSU_CONTEXT to answer.\n"
    "Do NOT generate random or outside information.\n"
    "Always give short, accurate answers (max 2 lines).\n"
    "Be helpful like a real admission counsellor.\n\n"
    + SGSU_CONTEXT
)

HINDI_KEYWORD_MAP = {
    "एडमिशन": "admission",
    "प्रवेश": "admission",
    "कोर्स": "course",
    "कोर्सेस": "courses",
    "फीस": "fees",
    "कॉलेज": "college",
    "फैकल्टी": "faculty",
    "चांसलर": "chancellor",
    "वाइस चांसलर": "vice chancellor",
    "रजिस्ट्रार": "registrar",
    "लोकेशन": "location",
    "पता": "address",
    "संपर्क": "contact",
    "कॉन्टैक्ट": "contact",
}

FALLBACK_OPTIONS = [
    "Aap SGSU ke admission, courses, faculty ya placement ke bare me pooch sakte ho.",
    "Aap SGSU ke admission, courses, faculty ya placement ke bare me pooch sakte ho.",
    "Aap SGSU ke admission, courses, faculty ya placement ke bare me pooch sakte ho.",
]

app = FastAPI(title="AI University Counsellor API")
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
    source: str


def load_local_env() -> None:
    try:
        if not os.path.exists(ENV_PATH):
            return
        with open(ENV_PATH, "r", encoding="utf-8") as env_file:
            for raw_line in env_file:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception as ex:
        logger.exception("Local env load failed: %s", ex)


load_local_env()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY", "").strip()


def detect_language(message: str) -> str:
    return "hi" if re.search(r"[\u0900-\u097F]", message or "") else "hinglish"


def normalize_question(message: str) -> str:
    try:
        normalized = (message or "").strip().lower()
        for source_text, target_text in HINDI_KEYWORD_MAP.items():
            normalized = normalized.replace(source_text.lower(), target_text)
        normalized = re.sub(r"[^\w\s]", " ", normalized)
        normalized = " ".join(normalized.split())
        return normalized
    except Exception:
        return (message or "").strip().lower()


def init_db() -> None:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question TEXT UNIQUE,
                    answer TEXT
                )
                """
            )
            conn.commit()
    except Exception as ex:
        logger.exception("DB init failed: %s", ex)


def get_cached_answer(question: str) -> Optional[str]:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT answer FROM chat_cache WHERE question = ? LIMIT 1", (question,))
            row = cursor.fetchone()
            return row[0] if row else None
    except Exception as ex:
        logger.exception("DB read failed: %s", ex)
        return None


def save_to_cache(question: str, answer: str) -> None:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO chat_cache(question, answer) VALUES (?, ?)",
                (question, answer),
            )
            conn.commit()
    except Exception as ex:
        logger.exception("DB write failed: %s", ex)


def detect_intent(normalized_message: str) -> str:
    if "admission" in normalized_message or "apply" in normalized_message:
        return "admission"
    if "course" in normalized_message or "courses" in normalized_message or "branch" in normalized_message:
        return "courses"
    if "fees" in normalized_message or "fee" in normalized_message:
        return "fees"
    if "chancellor" in normalized_message:
        return "chancellor"
    if "vice chancellor" in normalized_message:
        return "vice_chancellor"
    if "registrar" in normalized_message:
        return "registrar"
    if "dean" in normalized_message or "faculty" in normalized_message or "department" in normalized_message:
        return "faculty"
    if "teacher" in normalized_message or "staff" in normalized_message:
        return "staff"
    if "location" in normalized_message or "address" in normalized_message:
        return "location"
    if "contact" in normalized_message:
        return "contact"
    return ""


def format_reply(hinglish_text: str, hindi_text: str, lang: str) -> str:
    reply = hindi_text if lang == "hi" else hinglish_text
    reply = " ".join(reply.split())
    return reply[:180]


def get_intent_response(intent: str, lang: str) -> str:
    answers = {
        "admission": (
            "SGSU me admission merit based hota hai. Aap 12th ya graduation marks ke basis pe official website se apply kar sakte ho.",
            "SGSU में admission merit based होता है। आप 12वीं या graduation marks के basis पर official website से apply कर सकते हैं।",
        ),
        "courses": (
            "SGSU me B.Tech (CSE, AI/ML), BCA, BBA, B.Sc aur dusre programs available hai.",
            "SGSU में B.Tech (CSE, AI/ML), BCA, BBA, B.Sc और दूसरे programs available हैं।",
        ),
        "fees": (
            "SGSU me fees course ke hisab se vary karti hai, approx 40K se 3.2 lakh tak.",
            "SGSU में fees course के हिसाब से vary करती है, approx 40K से 3.2 lakh तक।",
        ),
        "chancellor": (
            "SGSU ke Chancellor Dr. Siddharth Chaturvedi hai.",
            "SGSU के Chancellor Dr. Siddharth Chaturvedi हैं।",
        ),
        "vice_chancellor": (
            "Official SGSU pages me Vice Chancellor ke liye Dr. Ajay Bhushan ka naam milta hai. Ek 10 January 2025 news post me Dr. Vijay Singh ka naam bhi diya gaya hai.",
            "Official SGSU pages में Vice Chancellor के लिए Dr. Ajay Bhushan का नाम मिलता है। 10 January 2025 की एक news post में Dr. Vijay Singh का नाम भी दिया गया है।",
        ),
        "registrar": (
            "Official SGSU references me Registrar ka naam Dr. Sitesh Sinha diya gaya hai.",
            "Official SGSU references में Registrar का नाम Dr. Sitesh Sinha दिया गया है।",
        ),
        "faculty": (
            "SGSU me Engineering & Technology, Management, IT, Science, Humanities, Future Skills aur Agriculture jaise faculties available hai.",
            "SGSU में Engineering & Technology, Management, IT, Science, Humanities, Future Skills और Agriculture जैसी faculties available हैं।",
        ),
        "staff": (
            "SGSU me faculty aur staff alag-alag academic areas me available hai. Specific department poochoge to main better guide kar dunga.",
            "SGSU में faculty और staff अलग-अलग academic areas में available हैं। Specific department पूछोगे तो मैं better guide कर दूँगा।",
        ),
        "location": (
            "SGSU ka campus SCOPE Campus, NH-12, Near Misrod, Hoshangabad Road, Bhopal me hai.",
            "SGSU का campus SCOPE Campus, NH-12, Near Misrod, Hoshangabad Road, Bhopal में है।",
        ),
        "contact": (
            "SGSU contact: +91-7552432903/904, info@sgsuniversity.ac.in.",
            "SGSU contact: +91-7552432903/904, info@sgsuniversity.ac.in।",
        ),
    }
    hinglish_text, hindi_text = answers.get(intent, FALLBACK_OPTIONS[0])
    return format_reply(hinglish_text, hindi_text, lang)


def get_fallback_response(lang: str) -> str:
    hinglish = random.choice(FALLBACK_OPTIONS)
    hindi = "आप SGSU के admission, courses, faculty या placement के बारे में पूछ सकते हैं।"
    return format_reply(hinglish, hindi, lang)


def build_model_prompt(message: str, lang: str) -> str:
    language_line = (
        "Reply only in Hindi written in Devanagari script."
        if lang == "hi"
        else "Reply only in Hinglish using Hindi in English letters."
    )
    return SYSTEM_PROMPT + "\n" + language_line + "\nUser: " + message + "\nCounsellor:"


def _call_gemini(full_prompt: str) -> Optional[str]:
    try:
        if not GEMINI_API_KEY:
            return None
        response = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent",
            params={"key": GEMINI_API_KEY},
            headers={"Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": full_prompt}]}]},
            timeout=15,
        )
        if response.status_code != 200:
            return None
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception:
        return None


def _call_huggingface(full_prompt: str) -> Optional[str]:
    try:
        if not HUGGINGFACE_API_KEY:
            return None
        response = requests.post(
            HUGGINGFACE_MODEL_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {HUGGINGFACE_API_KEY}",
            },
            json={
                "model": HUGGINGFACE_MODEL_NAME,
                "messages": [{"role": "user", "content": full_prompt[:3500]}],
                "temperature": 0.3,
                "max_tokens": 60,
            },
            timeout=20,
        )
        if response.status_code != 200:
            return None
        data = response.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "").strip() or None
    except Exception:
        return None


def clean_model_reply(text: str) -> str:
    cleaned = " ".join((text or "").replace("\r", " ").replace("\n", " ").split()).strip()
    for marker in ("User:", "Counsellor:", "Assistant:", "Answer:"):
        if marker in cleaned:
            cleaned = cleaned.split(marker, 1)[0].strip()
    parts = re.split(r"(?<=[.!?।])\s+", cleaned)
    return " ".join(parts[:2])[:180]


def is_low_quality_reply(text: str) -> bool:
    cleaned = (text or "").strip().lower()
    return not cleaned or cleaned.endswith("?") or len(cleaned.split()) <= 2


def is_valid_reply(text: str) -> bool:
    cleaned = (text or "").strip().lower()
    if not cleaned:
        return False
    if any(token in cleaned for token in {"google", "weather", "movie", "bitcoin", "stock"}):
        return False
    keywords = {"sgsu", "admission", "course", "fees", "faculty", "chancellor", "registrar", "bhopal", "website"}
    return any(keyword in cleaned for keyword in keywords)


def log_result(message: str, normalized_message: str, intent: str, lang: str, source: str, reply: str) -> None:
    print("RAW:", message)
    print("NORMALIZED:", normalized_message)
    print("INTENT:", intent)
    print("LANG:", lang)
    print("SOURCE:", source)
    print("REPLY:", reply)


def resolve_response(message: str) -> tuple[str, str]:
    normalized_message = normalize_question(message)
    lang = detect_language(message)
    intent = detect_intent(normalized_message)

    if intent:
        reply = get_intent_response(intent, lang)
        log_result(message, normalized_message, intent, lang, "intent", reply)
        return "intent", reply

    cached_reply = get_cached_answer(normalized_message)
    if cached_reply:
        cached_reply = clean_model_reply(cached_reply)
        if cached_reply and not is_low_quality_reply(cached_reply) and is_valid_reply(cached_reply):
            log_result(message, normalized_message, intent, lang, "cache", cached_reply)
            return "cache", cached_reply

    full_prompt = build_model_prompt(message, lang)

    gemini_reply = clean_model_reply(_call_gemini(full_prompt) or "")
    if gemini_reply and not is_low_quality_reply(gemini_reply) and is_valid_reply(gemini_reply):
        save_to_cache(normalized_message, gemini_reply)
        log_result(message, normalized_message, intent, lang, "gemini", gemini_reply)
        return "gemini", gemini_reply

    hf_reply = clean_model_reply(_call_huggingface(full_prompt) or "")
    if hf_reply and not is_low_quality_reply(hf_reply) and is_valid_reply(hf_reply):
        save_to_cache(normalized_message, hf_reply)
        log_result(message, normalized_message, intent, lang, "hf", hf_reply)
        return "hf", hf_reply

    fallback_reply = get_fallback_response(lang)
    save_to_cache(normalized_message, fallback_reply)
    log_result(message, normalized_message, intent, lang, "fallback", fallback_reply)
    return "fallback", fallback_reply


@app.on_event("startup")
def startup_event() -> None:
    init_db()


@app.get("/")
def health_check() -> dict:
    return {"status": "ok", "message": "AI Counsellor backend running"}


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    user_message = (payload.message or "").strip()
    if not user_message:
        return ChatResponse(reply="Please type your question.", source="fallback")
    source, reply = resolve_response(user_message)
    return ChatResponse(reply=reply, source=source)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="debug")

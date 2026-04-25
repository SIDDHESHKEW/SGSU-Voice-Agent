import React, { useEffect, useRef, useState } from "react";

const CHAT_API_URL = "http://localhost:8000/chat";

const ROMAN_HINDI_MAP = {
  namaste: "नमस्ते",
  main: "मैं",
  mai: "मैं",
  mera: "मेरा",
  meri: "मेरी",
  mujhe: "मुझे",
  aap: "आप",
  aapka: "आपका",
  aapki: "आपकी",
  kya: "क्या",
  kaise: "कैसे",
  kahan: "कहां",
  yahan: "यहां",
  hai: "है",
  hoon: "हूं",
  hu: "हूं",
  hain: "हैं",
  haan: "हां",
  nahi: "नहीं",
  aur: "और",
  ya: "या",
  ke: "के",
  ki: "की",
  ka: "का",
  se: "से",
  mein: "में",
  tum: "तुम",
  karo: "करो",
  karun: "करूं",
  karu: "करूं",
  karna: "करना",
  bol: "बोल",
  bolo: "बोलो",
  pooch: "पूछ",
  poochiye: "पूछिए",
  batao: "बताओ",
  bataye: "बताएं",
  bilkul: "बिलकुल",
  shukriya: "शुक्रिया",
  dhanyavaad: "धन्यवाद",
  admission: "admission",
  course: "course",
  courses: "courses",
  fees: "fees",
  university: "university",
  counsellor: "counsellor",
};

function VoiceAssistant() {
  const [status, setStatus] = useState("Idle");
  const [isListening, setIsListening] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [messages, setMessages] = useState([
    { role: "assistant", text: "Hi! Ask me about courses, admission, fees, placements, or location." },
  ]);

  const recognitionRef = useRef(null);
  const keepListeningRef = useRef(false);
  const isBusyRef = useRef(false);
  const selectedVoiceRef = useRef(null);
  const listeningLangRef = useRef("hi-IN");

  const selectSingleFriendlyVoice = () => {
    try {
      const voices = window.speechSynthesis?.getVoices?.() || [];
      if (!voices.length) return;

      const findByLang = (lang) => voices.find((v) => v.lang?.toLowerCase() === lang);
      const findStarts = (prefix) => voices.find((v) => v.lang?.toLowerCase().startsWith(prefix));

      const chosen =
        findByLang("hi-in") ||
        findByLang("en-in") ||
        findStarts("hi") ||
        findStarts("en") ||
        voices[0];

      selectedVoiceRef.current = chosen;
      listeningLangRef.current = chosen?.lang?.toLowerCase().startsWith("hi") ? "hi-IN" : "en-IN";
      console.log("[VoiceAssistant] selected voice:", chosen?.name, chosen?.lang);
    } catch (error) {
      console.error("[VoiceAssistant] voice selection failed:", error);
    }
  };

  const normalizeDisplayText = (input) => {
    try {
      if (!input) return "";

      return input
        .split(/(\s+)/)
        .map((segment) => {
          if (!segment.trim()) return segment;

          const leading = (segment.match(/^[^A-Za-z\u0900-\u097F0-9]*/) || [""])[0];
          const trailing = (segment.match(/[^A-Za-z\u0900-\u097F0-9]*$/) || [""])[0];
          const core = segment.slice(leading.length, segment.length - trailing.length);

          if (!core) return segment;
          const lower = core.toLowerCase();

          if (/[\u0900-\u097F]/.test(core)) return segment;

          if (ROMAN_HINDI_MAP[lower]) {
            return `${leading}${ROMAN_HINDI_MAP[lower]}${trailing}`;
          }

          return segment;
        })
        .join("");
    } catch (error) {
      return input;
    }
  };

  // Section 1: Small helper to add chat messages.
  const addMessage = (role, text) => {
    setMessages((prev) => [...prev, { role, text: normalizeDisplayText(text) }]);
  };

  // Section 2: Call backend API for AI response.
  const getAIAnswer = async (question) => {
    try {
      console.log("[VoiceAssistant] API request:", { url: CHAT_API_URL, message: question });

      const response = await fetch(CHAT_API_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({ message: question }),
      });

      if (!response.ok) {
        throw new Error(`Backend API error: ${response.status}`);
      }

      const data = await response.json();
      console.log("[VoiceAssistant] API response:", data);
      const text = data?.reply?.trim();

      if (!text) {
        throw new Error("Empty AI response");
      }

      return text;
    } catch (error) {
      console.error("[VoiceAssistant] API error:", error);
      return "Server not available";
    }
  };

  const startRecognition = () => {
    try {
      if (!recognitionRef.current || isBusyRef.current) return;
      recognitionRef.current.lang = listeningLangRef.current;
      recognitionRef.current.start();
    } catch (error) {
      // start can throw if called too quickly; keep session alive and retry on next onend.
    }
  };

  const stopRecognition = () => {
    try {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
    } catch (error) {
      // Ignore stop race errors.
    }
  };

  // Section 4: Speak assistant output with one fixed friendly voice.
  const speak = (text) =>
    new Promise((resolve) => {
    try {
      if (!window.speechSynthesis) return;
      window.speechSynthesis.cancel();

      const utterance = new SpeechSynthesisUtterance(text);
      const selectedVoice = selectedVoiceRef.current;

      if (selectedVoice) {
        utterance.voice = selectedVoice;
        utterance.lang = selectedVoice.lang;
      } else {
        utterance.lang = listeningLangRef.current;
      }

      utterance.rate = 0.9;
      utterance.pitch = 1;
      utterance.onstart = () => setStatus("Speaking");
      utterance.onend = () => {
        setStatus(keepListeningRef.current ? "Listening" : "Idle");
        resolve();
      };
      utterance.onerror = () => {
        setStatus(keepListeningRef.current ? "Listening" : "Idle");
        resolve();
      };

      window.speechSynthesis.speak(utterance);
    } catch (error) {
      setStatus(keepListeningRef.current ? "Listening" : "Idle");
      resolve();
    }
  });

  // Section 5: Process user speech end-to-end.
  const handleUserSpeech = async (text) => {
    if (!text || isBusyRef.current) return;

    isBusyRef.current = true;
    stopRecognition();
    setIsListening(false);

    console.log("[VoiceAssistant] user speech:", text);
    addMessage("user", text);
    setIsLoading(true);
    setStatus("Thinking...");

    try {
      const answer = await getAIAnswer(text);
      console.log("[VoiceAssistant] AI response:", answer);
      addMessage("assistant", answer);
      await speak(answer);
    } finally {
      setIsLoading(false);
      isBusyRef.current = false;

      if (keepListeningRef.current) {
        startRecognition();
      } else {
        setStatus("Idle");
      }
    }
  };

  // Section 6: Setup SpeechRecognition once.
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      addMessage("assistant", "Speech recognition is not supported in this browser.");
      return undefined;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = listeningLangRef.current;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      console.log("[VoiceAssistant] mic start");
      setIsListening(true);
      setStatus("Listening");
    };

    recognition.onresult = (event) => {
      const lastIndex = event.results.length - 1;
      const spokenText = event.results[lastIndex][0]?.transcript?.trim();
      if (spokenText) {
        void handleUserSpeech(spokenText);
      }
    };

    recognition.onerror = (event) => {
      if (event.error === "not-allowed") {
        keepListeningRef.current = false;
        addMessage("assistant", "Microphone permission denied. Please allow microphone access.");
      } else if (event.error === "no-speech") {
        if (keepListeningRef.current && !isBusyRef.current) {
          setTimeout(() => startRecognition(), 220);
        }
      } else {
        addMessage("assistant", "Voice recognition error. Please try again.");
        if (keepListeningRef.current && !isBusyRef.current) {
          setTimeout(() => startRecognition(), 300);
        }
      }

      if (!keepListeningRef.current) {
        setStatus("Idle");
      }
      setIsListening(false);
    };

    recognition.onend = () => {
      setIsListening(false);

      if (keepListeningRef.current && !isBusyRef.current) {
        setTimeout(() => startRecognition(), 250);
      } else if (!keepListeningRef.current) {
        setStatus("Idle");
      }
    };

    recognitionRef.current = recognition;

    return () => {
      try {
        recognition.stop();
      } catch (error) {
        // Ignore cleanup errors.
      }
      keepListeningRef.current = false;
      if (window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  useEffect(() => {
    const handleVoicesChanged = () => {
      selectSingleFriendlyVoice();
    };

    try {
      window.speechSynthesis?.addEventListener?.("voiceschanged", handleVoicesChanged);
      handleVoicesChanged();
    } catch (error) {
      // Ignore unsupported event errors.
    }

    return () => {
      try {
        window.speechSynthesis?.removeEventListener?.("voiceschanged", handleVoicesChanged);
      } catch (error) {
        // Ignore cleanup errors.
      }
    };
  }, []);

  // Section 7: Toggle microphone start/stop.
  const toggleListening = () => {
    if (!recognitionRef.current) return;

    if (keepListeningRef.current) {
      keepListeningRef.current = false;
      stopRecognition();
      window.speechSynthesis?.cancel?.();
      setIsListening(false);
      setStatus("Idle");
    } else {
      keepListeningRef.current = true;
      startRecognition();
    }
  };

  return (
    <section className="voice-card">
      <div className="voice-top">
        <button className={`mic-btn ${isListening ? "active" : ""}`} onClick={toggleListening} type="button">
          {isListening ? "Stop Mic" : "Start Mic"}
        </button>
        <span className="status-pill">Status: {isLoading ? "Thinking..." : status}</span>
      </div>

      <div className="chat-box">
        {messages.map((item, idx) => (
          <p key={`${item.role}-${idx}`} className={`chat-line ${item.role}`}>
            <strong>{item.role === "assistant" ? "Counsellor" : "You"}:</strong> {item.text}
          </p>
        ))}
      </div>
    </section>
  );
}

export default VoiceAssistant;
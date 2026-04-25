import React, { useEffect, useRef, useState } from "react";

const CHAT_API_URL = "http://localhost:8000/chat";

function VoiceAssistant() {
  const [status, setStatus] = useState("Idle");
  const [isListening, setIsListening] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [messages, setMessages] = useState([
    { role: "assistant", text: "Hi! Ask me about courses, admission, fees, placements, or location." },
  ]);

  const recognitionRef = useRef(null);

  // Section 1: Small helper to add chat messages.
  const addMessage = (role, text) => {
    setMessages((prev) => [...prev, { role, text }]);
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

  // Section 4: Speak assistant output.
  const speak = (text) => {
    try {
      if (!window.speechSynthesis) return;
      window.speechSynthesis.cancel();

      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = "en-IN";
      utterance.rate = 0.95;
      utterance.onstart = () => setStatus("Speaking");
      utterance.onend = () => setStatus(isListening ? "Listening" : "Idle");
      utterance.onerror = () => setStatus(isListening ? "Listening" : "Idle");

      window.speechSynthesis.speak(utterance);
    } catch (error) {
      setStatus(isListening ? "Listening" : "Idle");
    }
  };

  // Section 5: Process user speech end-to-end.
  const handleUserSpeech = async (text) => {
    console.log("[VoiceAssistant] user speech:", text);
    addMessage("user", text);
    setIsLoading(true);
    setStatus("Thinking...");

    const answer = await getAIAnswer(text);
    console.log("[VoiceAssistant] AI response:", answer);
    addMessage("assistant", answer);
    setIsLoading(false);
    speak(answer);
  };

  // Section 6: Setup SpeechRecognition once.
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      addMessage("assistant", "Speech recognition is not supported in this browser.");
      return undefined;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.lang = "en-IN";

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
        addMessage("assistant", "Microphone permission denied. Please allow microphone access.");
      } else if (event.error === "no-speech") {
        addMessage("assistant", "No speech detected. Please try again.");
      } else {
        addMessage("assistant", "Voice recognition error. Please try again.");
      }
      setStatus("Idle");
      setIsListening(false);
    };

    recognition.onend = () => {
      setIsListening(false);
      setStatus("Idle");
    };

    recognitionRef.current = recognition;

    return () => {
      try {
        recognition.stop();
      } catch (error) {
        // Ignore cleanup errors.
      }
      if (window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  // Section 7: Toggle microphone start/stop.
  const toggleListening = () => {
    if (!recognitionRef.current) return;

    if (isListening) {
      recognitionRef.current.stop();
      setIsListening(false);
      setStatus("Idle");
    } else {
      try {
        recognitionRef.current.start();
      } catch (error) {
        addMessage("assistant", "Could not start microphone. Please retry.");
      }
    }
  };

  return (
    <section className="voice-card">
      <div className="voice-top">
        <button className="mic-btn" onClick={toggleListening} type="button">
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
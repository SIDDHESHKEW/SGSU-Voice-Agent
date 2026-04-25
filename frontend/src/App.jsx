import React from "react";
import VoiceAssistant from "./VoiceAssistant";
import "./styles.css";

function App() {
  return (
    <main className="app-page">
      <header className="app-header">
        <h1>Scope Global Skills University</h1>
        <p>AI Voice Counsellor</p>
      </header>

      <VoiceAssistant />
    </main>
  );
}

export default App;

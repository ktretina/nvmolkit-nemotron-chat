import { FormEvent, useEffect, useState } from "react";

import AdaptiveViewer from "./AdaptiveViewer";
import { clearSession, getSession, sendMessage, sendSuggestedPrompt, setSessionKey } from "./api";
import type { PromptId, Visualization } from "./types";
import "./styles.css";

const SUGGESTED_PROMPTS: Array<{ id: PromptId; label: string }> = [
  { id: "fingerprints", label: "Profile fingerprint density" },
  { id: "similarity", label: "Map structural similarity" },
  { id: "clusters", label: "Find molecular clusters" },
  { id: "conformers", label: "Explore low-energy conformers" },
];

interface ChatEntry {
  id: number;
  role: "user" | "assistant";
  text: string;
}

export default function App() {
  const [checkingSession, setCheckingSession] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [message, setMessage] = useState("");
  const [entries, setEntries] = useState<ChatEntry[]>([]);
  const [visualization, setVisualization] = useState<Visualization | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    getSession()
      .then((session) => {
        if (!active) return;
        setAuthenticated(session.authenticated);
        setVisualization(session.visualization);
      })
      .catch(() => {
        if (active) setError("The session could not be checked.");
      })
      .finally(() => {
        if (active) setCheckingSession(false);
      });
    return () => { active = false; };
  }, []);

  async function submitKey(event: FormEvent) {
    event.preventDefault();
    const candidate = apiKey.trim();
    if (!candidate || busy) return;
    setBusy(true);
    setError(null);
    try {
      await setSessionKey(candidate);
      setApiKey("");
      setAuthenticated(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The session could not be started.");
    } finally {
      setBusy(false);
    }
  }

  async function runAnalysis(input: { promptId: PromptId; label: string } | { message: string }) {
    if (busy) return;
    const userText = "message" in input ? input.message : input.label;
    setEntries((current) => [...current, { id: Date.now(), role: "user", text: userText }]);
    setBusy(true);
    setError(null);
    try {
      const result = "message" in input
        ? await sendMessage(input.message)
        : await sendSuggestedPrompt(input.promptId);
      setVisualization(result.visualization);
      const unavailable = result.visualization.interpretation_unavailable;
      const interpretation = result.visualization.interpretation;
      setEntries((current) => [...current, {
        id: Date.now() + 1,
        role: "assistant",
        text: unavailable
          ? "The figure is ready. Nemotron interpretation is temporarily unavailable."
          : interpretation || "The requested bundled-data figure is ready.",
      }]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The analysis could not be completed.");
    } finally {
      setBusy(false);
    }
  }

  function submitMessage(event: FormEvent) {
    event.preventDefault();
    const trimmed = message.trim();
    if (!trimmed || busy) return;
    setMessage("");
    void runAnalysis({ message: trimmed });
  }

  async function logout() {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await clearSession();
      setAuthenticated(false);
      setVisualization(null);
      setEntries([]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The session could not be cleared.");
    } finally {
      setBusy(false);
    }
  }

  if (checkingSession) {
    return <main className="session-loading" aria-busy="true"><p>Checking session…</p></main>;
  }

  if (!authenticated) {
    return (
      <main className="key-gate">
        <form className="key-card" onSubmit={submitKey}>
          <p className="eyebrow">nvMolKit + Nemotron</p>
          <h1>Explore bundled molecular data</h1>
          <p>Your key is held only in server memory for this ephemeral session. It is never stored in the browser.</p>
          <label htmlFor="api-key">NVIDIA API key</label>
          <input
            id="api-key"
            type="password"
            autoComplete="off"
            value={apiKey}
            onChange={(event) => setApiKey(event.target.value)}
            disabled={busy}
          />
          <button type="submit" disabled={busy || !apiKey.trim()}>{busy ? "Starting…" : "Start session"}</button>
          {error && <p role="alert" className="error-message">{error}</p>}
        </form>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <section className="chat-pane" aria-label="Molecular analysis chat">
        <header className="chat-header">
          <div><p className="eyebrow">nvMolKit</p><h1>Molecular explorer</h1></div>
          <button className="text-button" type="button" onClick={() => void logout()} disabled={busy}>Clear session</button>
        </header>
        <div className="conversation">
          <div className="welcome">
            <h2>Analyze the bundled ChEMBL sample</h2>
            <p>Choose a validated workflow or ask Nemotron to select one of the same four bounded nvMolKit analyses.</p>
          </div>
          <div className="suggested-prompts" aria-label="Suggested analyses">
            {SUGGESTED_PROMPTS.map((prompt) => (
              <button
                key={prompt.id}
                type="button"
                data-testid="suggested-prompt"
                disabled={busy}
                onClick={() => void runAnalysis({ promptId: prompt.id, label: prompt.label })}
              >
                {prompt.label}
              </button>
            ))}
          </div>
          <div className="messages" aria-label="Conversation history">
            {entries.map((entry) => <p key={entry.id} className={`message ${entry.role}`}>{entry.text}</p>)}
          </div>
        </div>
        <div className="request-status" role="status" aria-live="polite">
          {busy ? "Computing the molecular analysis…" : "Ready"}
        </div>
        {error && <p role="alert" className="error-message pane-error">{error}</p>}
        <form className="chat-form" onSubmit={submitMessage}>
          <label htmlFor="chat-message" className="sr-only">Ask about the bundled molecules</label>
          <textarea
            id="chat-message"
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder="Ask about the bundled molecules…"
            maxLength={2000}
            rows={2}
            disabled={busy}
          />
          <button type="submit" aria-label="Send message" disabled={busy || !message.trim()}>Send</button>
        </form>
        <p className="boundary-note">Research visualization only. Results use the bundled dataset and are not medical guidance.</p>
      </section>
      <section className="viewer-pane" aria-label="Scientific visualization">
        <AdaptiveViewer visualization={visualization} />
      </section>
    </main>
  );
}

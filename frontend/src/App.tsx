import { FormEvent, useEffect, useState } from "react";

import AdaptiveViewer from "./AdaptiveViewer";
import {
  ApiError,
  endSession,
  getSession,
  resetWorkspace,
  sendMessage,
  sendSuggestedPrompt,
  setSessionKey,
} from "./api";
import type { PromptId, ProviderStatus, Visualization } from "./types";
import "./styles.css";

const SUGGESTED_PROMPTS: Array<{ id: PromptId; label: string }> = [
  { id: "fingerprints", label: "Show the Morgan fingerprint density across the bundled molecules." },
  { id: "similarity", label: "Map structural similarity across the bundled dataset." },
  { id: "clusters", label: "Cluster the molecules by structural similarity and show the cluster sizes." },
  { id: "conformers", label: "Generate and compare optimized 3D conformers for representative molecules." },
];

const ANALYSIS_FUNCTIONS: Record<Visualization["kind"], string> = {
  fingerprint_density: "analyze_fingerprint_density",
  similarity: "analyze_similarity_map",
  clusters: "analyze_cluster_distribution",
  conformers: "analyze_representative_conformers",
};

const PROVIDER_MESSAGES: Record<ProviderStatus, string | null> = {
  unchecked: "Nemotron will be checked on the first hosted request.",
  available: null,
  authentication_failed: "Nemotron rejected the API key. End the session and enter a valid key.",
  rate_limited: "Nemotron rate-limited the request. Try again later.",
  provider_unavailable: "Nemotron is temporarily unavailable.",
  model_unavailable: "The configured Nemotron model is unavailable.",
  invalid_response: "Nemotron returned a response outside the supported bounded analyses.",
};

interface ChatEntry {
  id: number;
  role: "user" | "assistant";
  text: string;
}

interface FigureContext {
  functionName: string;
  requestText: string;
}

export default function App() {
  const [checkingSession, setCheckingSession] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [message, setMessage] = useState("");
  const [entries, setEntries] = useState<ChatEntry[]>([]);
  const [visualization, setVisualization] = useState<Visualization | null>(null);
  const [figureContext, setFigureContext] = useState<FigureContext | null>(null);
  const [failedRequest, setFailedRequest] = useState<string | null>(null);
  const [chatStarted, setChatStarted] = useState(false);
  const [providerStatus, setProviderStatus] = useState<ProviderStatus>("unchecked");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    getSession()
      .then((session) => {
        if (!active) return;
        setAuthenticated(session.authenticated);
        setVisualization(session.visualization);
        setProviderStatus(session.provider_status);
        if (session.visualization) {
          setFigureContext({
            functionName: ANALYSIS_FUNCTIONS[session.visualization.kind],
            requestText: "Previous successful request",
          });
          setChatStarted(true);
        }
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
      const workspace = await setSessionKey(candidate);
      setApiKey("");
      setAuthenticated(workspace.authenticated);
      setProviderStatus(workspace.provider_status);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The session could not be started.");
    } finally {
      setBusy(false);
    }
  }

  async function runAnalysis(input: { promptId: PromptId; label: string } | { message: string }) {
    if (busy) return;
    const userText = "message" in input ? input.message : input.label;
    setChatStarted(true);
    setEntries((current) => [...current, { id: Date.now(), role: "user", text: userText }]);
    setBusy(true);
    setError(null);
    try {
      const result = "message" in input
        ? await sendMessage(input.message)
        : await sendSuggestedPrompt(input.promptId);
      setVisualization(result.visualization);
      setProviderStatus(result.provider_status);
      setFigureContext({
        functionName: ANALYSIS_FUNCTIONS[result.visualization.kind],
        requestText: userText,
      });
      setFailedRequest(null);
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
      if (visualization) setFailedRequest(userText);
      if (caught instanceof ApiError && caught.providerStatus) {
        setProviderStatus(caught.providerStatus);
        setError(null);
      } else {
        setError(caught instanceof Error ? caught.message : "The analysis could not be completed.");
      }
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

  async function newAnalysis() {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const reset = await resetWorkspace();
      setAuthenticated(reset.authenticated);
      setProviderStatus(reset.provider_status);
      setVisualization(null);
      setFigureContext(null);
      setFailedRequest(null);
      setChatStarted(false);
      setEntries([]);
      setMessage("");
    } catch (caught) {
      if (caught instanceof ApiError && caught.providerStatus) {
        setProviderStatus(caught.providerStatus);
        setError(null);
      } else {
        setError(caught instanceof Error ? caught.message : "The analysis workspace could not be reset.");
      }
    } finally {
      setBusy(false);
    }
  }

  async function endWorkspaceSession() {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await endSession();
      setAuthenticated(false);
      setProviderStatus("unchecked");
      setVisualization(null);
      setFigureContext(null);
      setFailedRequest(null);
      setChatStarted(false);
      setEntries([]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The session could not be ended.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className={checkingSession || !authenticated ? "session-shell" : "app-shell"}>
      {checkingSession ? (
        <section className="session-loading" aria-busy="true"><p>Checking session…</p></section>
      ) : !authenticated ? (
        <section className="key-gate">
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
            <button type="submit" disabled={busy || !apiKey.trim()}>{busy ? "Starting…" : "Start workspace"}</button>
            {error && <p role="alert" className="error-message">{error}</p>}
          </form>
        </section>
      ) : (
        <section className="chat-pane" aria-label="Molecular analysis chat">
        <header className="chat-header">
          <div><p className="eyebrow">nvMolKit</p><h1>Molecular explorer</h1></div>
          <div className="session-actions" aria-label="Workspace actions">
            <button className="text-button" type="button" onClick={() => void newAnalysis()} disabled={busy}>New analysis</button>
            <button className="text-button" type="button" onClick={() => void endWorkspaceSession()} disabled={busy}>End session</button>
          </div>
        </header>
        <div className="conversation">
          <div className="welcome">
            <h2>Analyze the bundled ChEMBL sample</h2>
            <p>Choose a validated workflow or ask Nemotron to select one of the same four bounded nvMolKit analyses.</p>
          </div>
          {!chatStarted && (
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
          )}
          <div className="messages" aria-label="Conversation history">
            {entries.map((entry) => <p key={entry.id} className={`message ${entry.role}`}>{entry.text}</p>)}
          </div>
        </div>
        {chatStarted && (
          <details className="compact-prompt-menu">
            <summary>Validated analyses</summary>
            <div>
              {SUGGESTED_PROMPTS.map((prompt) => (
                <button
                  key={prompt.id}
                  type="button"
                  disabled={busy}
                  onClick={() => void runAnalysis({ promptId: prompt.id, label: prompt.label })}
                >
                  {prompt.label}
                </button>
              ))}
            </div>
          </details>
        )}
        <div className="request-status" role="status" aria-live="polite">
          {busy ? "Computing the molecular analysis…" : "Ready"}
        </div>
        {PROVIDER_MESSAGES[providerStatus] && (
          <p className="provider-notice" role="status" aria-live="polite">
            {PROVIDER_MESSAGES[providerStatus]}
          </p>
        )}
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
      )}
      <section
        className={`viewer-pane${checkingSession || !authenticated ? " persistent-viewer-hidden" : ""}`}
        aria-label="Scientific visualization"
        aria-hidden={checkingSession || !authenticated}
      >
        {authenticated && figureContext && (
          <header className="viewer-header">
            <p>Producing nvMolKit analysis function</p>
            <h2>{figureContext.functionName}</h2>
            <p>Result for: “{figureContext.requestText}”</p>
            {failedRequest && (
              <p className="retained-result-note">
                Figure retained from the earlier successful request “{figureContext.requestText}”. Latest request failed: “{failedRequest}”.
              </p>
            )}
          </header>
        )}
        <div className="viewer-content">
          <AdaptiveViewer visualization={authenticated && !checkingSession ? visualization : null} />
        </div>
      </section>
    </main>
  );
}

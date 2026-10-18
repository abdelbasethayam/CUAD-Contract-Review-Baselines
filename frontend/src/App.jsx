import React, { Component, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { API_URL, appPath, forgetAnalysis, rememberAnalysis, savedAnalysisId } from "./lib/api.js";
import { buildReview } from "./lib/risk.js";
import { useMediaQuery } from "./lib/hooks.js";
import Intake from "./components/Intake.jsx";
import Progress from "./components/Progress.jsx";
import ContractBar from "./components/ContractBar.jsx";
import RiskReview from "./components/RiskReview.jsx";
import ClauseList from "./components/ClauseList.jsx";
import ChatPanel from "./components/ChatPanel.jsx";

class AppErrorBoundary extends Component {
  state = { error: null };
  static getDerivedStateFromError(error) { return { error }; }

  render() {
    if (this.state.error) {
      return (
        <main className="shell shell--narrow">
          <div className="notice notice--error" role="alert">
            <strong>Something went wrong while drawing this page.</strong> Refresh to try again. Your analysis is saved on the server.
          </div>
        </main>
      );
    }
    return this.props.children;
  }
}

function Header({ apiStatus, hasResult, onNew }) {
  return (
    <header className="topbar">
      <a className="wordmark" href={appPath("")} onClick={(event) => { if (hasResult) { event.preventDefault(); onNew(); } }}>
        <span className="wordmark__mark" aria-hidden="true">§</span>
        <span>Clausewise</span>
      </a>
      <div className="topbar__right">
        {apiStatus !== "online" && apiStatus !== "checking" && (
          <span className="status status--warn" role="status">
            {apiStatus === "offline" ? "Can't reach the analysis service" : "Analysis service needs attention"}
          </span>
        )}
        {hasResult && <button type="button" className="button button--quiet button--small" onClick={onNew}>New review</button>}
      </div>
    </header>
  );
}

function ContractReview() {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [trace, setTrace] = useState([]);
  const [elapsed, setElapsed] = useState(0);
  const [view, setView] = useState("risks");
  const [focus, setFocus] = useState(null);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [chatError, setChatError] = useState(null);
  const [demoLoading, setDemoLoading] = useState(false);
  const [apiStatus, setApiStatus] = useState("checking");
  const [restoring, setRestoring] = useState(false);
  const [activeRunId, setActiveRunId] = useState(null);
  const abortRef = useRef(null);
  const wide = useMediaQuery("(min-width: 1080px)");

  // Reopen a finished analysis from ?analysis_id= or from this browser session.
  useEffect(() => {
    const savedId = savedAnalysisId();
    if (!savedId) return undefined;
    let cancelled = false;
    setRestoring(true);
    fetch(appPath("documents/runs/" + encodeURIComponent(savedId)), { cache: "no-store" })
      .then(async (response) => {
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || "Saved analysis unavailable.");
        if (!cancelled && data.result_available && data.result) setResult(data.result);
      })
      .catch(() => forgetAnalysis())
      .finally(() => { if (!cancelled) setRestoring(false); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!loading) return undefined;
    const started = Date.now();
    const timer = window.setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => window.clearInterval(timer);
  }, [loading]);

  // The live stream is the main channel. Polling lets partial results appear and recovers from a dropped stream.
  useEffect(() => {
    if (!loading || !activeRunId) return undefined;
    let cancelled = false;
    let timerId = null;
    const poll = async () => {
      try {
        const response = await fetch(appPath("documents/runs/" + encodeURIComponent(activeRunId)), { cache: "no-store" });
        if (!response.ok) throw new Error("Run status unavailable");
        const data = await response.json();
        if (cancelled) return;
        if (data.result_available && data.result) {
          setResult({ ...data.result, partial: false });
        } else if (data.partial_result) {
          setResult((current) => (current?.analysis_id === activeRunId && !current.partial ? current : data.partial_result));
        }
      } catch { /* recovery path only */ }
      if (!cancelled) timerId = window.setTimeout(poll, 3500);
    };
    poll();
    return () => { cancelled = true; if (timerId) window.clearTimeout(timerId); };
  }, [loading, activeRunId]);

  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      try {
        const response = await fetch(appPath("health"), { cache: "no-store" });
        if (!response.ok) throw new Error("API unavailable");
        const data = await response.json();
        if (!cancelled) setApiStatus(data.status === "ok" ? "online" : "degraded");
      } catch {
        if (!cancelled) setApiStatus("offline");
      }
    };
    check();
    const id = window.setInterval(check, 15000);
    return () => { cancelled = true; window.clearInterval(id); };
  }, []);

  const resetWorkspace = useCallback(() => {
    abortRef.current?.abort();
    forgetAnalysis();
    setResult(null);
    setFile(null);
    setError(null);
    setTrace([]);
    setActiveRunId(null);
    setChatMessages([]);
    setChatError(null);
    setView("risks");
    setFocus(null);
  }, []);

  async function loadSample() {
    if (demoLoading || loading) return;
    setDemoLoading(true);
    setError(null);
    setChatError(null);
    setChatMessages([]);
    setTrace([]);
    try {
      const response = await fetch(appPath("query/demo-analysis"));
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "The sample contract is unavailable right now.");
      setResult(data);
      setView("risks");
      setFocus(null);
    } catch (err) {
      setError(err.message || "Could not open the sample contract.");
    } finally {
      setDemoLoading(false);
    }
  }

  async function askContract(question) {
    const text = String(question || "").trim();
    if (!result?.analysis_id || result.partial || loading || !text || chatLoading) return;
    const history = chatMessages.slice(-8)
      .map((message) => ({ role: message.role, content: message.role === "user" ? message.text : (message.answer || "") }))
      .filter((message) => message.content.trim());
    setChatMessages((messages) => [...messages, { role: "user", text }]);
    setChatError(null);
    setChatLoading(true);
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 90000);
    try {
      const response = await fetch(appPath("query/contract"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: controller.signal,
        body: JSON.stringify({ analysis_id: result.analysis_id, question: text, history }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || ("The assistant could not answer (" + response.status + ")."));
      setChatMessages((messages) => [...messages, { role: "assistant", ...data }]);
    } catch (err) {
      setChatError(err.name === "AbortError" ? "The assistant took too long to answer. Try again, or ask a narrower question." : (err.message || "The assistant could not answer this question."));
    } finally {
      window.clearTimeout(timeout);
      setChatLoading(false);
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setActiveRunId(null);
    forgetAnalysis();
    setTrace([]);
    setChatMessages([]);
    setChatError(null);
    setView("risks");
    setFocus(null);
    setElapsed(0);
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const formData = new FormData();
      formData.append("file", file);
      const response = await fetch(API_URL, { method: "POST", body: formData, signal: controller.signal });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || ("The upload failed (" + response.status + ")."));
      }
      if (!response.body) throw new Error("The server did not return a progress stream.");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let gotResult = false;

      const handleEvent = (raw) => {
        const line = raw.split("\n").find((item) => item.startsWith("data:"));
        if (!line) return;
        const evt = JSON.parse(line.slice(5).trim());
        if (evt.type === "progress") {
          setTrace((items) => [...items, evt]);
          if (evt.analysis_id) { setActiveRunId(evt.analysis_id); rememberAnalysis(evt.analysis_id); }
        } else if (evt.type === "result") {
          setResult({ ...evt.data, partial: false });
          if (evt.data?.analysis_id) { setActiveRunId(evt.data.analysis_id); rememberAnalysis(evt.data.analysis_id); }
          gotResult = true;
        } else if (evt.type === "error") {
          throw new Error(evt.message || "The analysis failed.");
        }
      };

      while (true) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
        const events = buffer.split("\n\n");
        buffer = events.pop() || "";
        events.forEach(handleEvent);
        if (done) break;
      }
      if (buffer.trim()) handleEvent(buffer);
      if (!gotResult) throw new Error("The analysis ended without a result. Please try again.");
    } catch (err) {
      setError(err.name === "AbortError" ? "Analysis cancelled. You can start it again at any time." : (err.message || "The analysis failed."));
    } finally {
      abortRef.current = null;
      setLoading(false);
    }
  }

  const clauses = result?.clauses || [];
  const review = useMemo(() => buildReview(result), [result]);
  const partial = Boolean(result?.partial);
  const chatDisabled = partial || loading || !result?.analysis_id;
  const activeView = wide && view === "ask" ? "risks" : view;
  const contractName = result?.contract_metadata?.name || result?.filename;

  function openClause(clauseIndex) {
    setFocus({ id: clauseIndex, token: Date.now() });
    setView("clauses");
    window.setTimeout(() => setFocus((current) => (current && current.id === clauseIndex ? null : current)), 4500);
  }

  const tabs = [
    ["risks", "Terms to review", review.total],
    ["clauses", "Clauses", clauses.length],
    ...(wide ? [] : [["ask", "Ask", null]]),
  ];

  const chat = (
    <ChatPanel
      name={contractName}
      messages={chatMessages}
      loading={chatLoading}
      error={chatError}
      disabled={chatDisabled}
      onAsk={askContract}
      onOpenClause={openClause}
      onClear={() => { setChatMessages([]); setChatError(null); }}
    />
  );

  return (
    <div className="app">
      <Header apiStatus={apiStatus} hasResult={Boolean(result) || loading} onNew={resetWorkspace} />

      {!result && !loading && (
        <main className="shell">
          <Intake file={file} setFile={setFile} loading={loading} demoLoading={demoLoading} restoring={restoring} onSubmit={handleSubmit} onDemo={loadSample} />
          {error && <div className="notice notice--error" role="alert">{error}</div>}
        </main>
      )}

      {loading && !result && (
        <main className="shell shell--narrow">
          <Progress trace={trace} elapsed={elapsed} onCancel={() => abortRef.current?.abort()} />
          {error && <div className="notice notice--error" role="alert">{error}</div>}
        </main>
      )}

      {result && (
        <main className="shell shell--workspace">
          <div className={"workspace" + (wide ? " workspace--split" : "")}>
            <div className="workspace__main">
              <ContractBar result={result} review={review} clauseCount={clauses.length} />

              {partial && (
                <div className="notice notice--live" role="status">
                  <i aria-hidden="true" />
                  <span><strong>Still analysing.</strong> Categories are ready. Flagged terms and answers will fill in when the checks finish{elapsed ? ` (${elapsed}s)` : ""}.</span>
                </div>
              )}
              {error && <div className="notice notice--error" role="alert">{error}</div>}

              <nav className="tabs" aria-label="Sections">
                {tabs.map(([key, label, count]) => (
                  <button key={key} type="button" className={"tab" + (activeView === key ? " tab--on" : "")} aria-current={activeView === key ? "page" : undefined} onClick={() => setView(key)}>
                    {label}{count != null && <span>{count}</span>}
                  </button>
                ))}
              </nav>

              {activeView === "risks" && <RiskReview review={review} clauses={clauses} onOpenClause={openClause} partial={partial} />}
              {activeView === "clauses" && <ClauseList clauses={clauses} perClause={review.perClause} focus={focus} onShowRisks={() => setView("risks")} />}
              {activeView === "ask" && chat}
            </div>
            {wide && <aside className="workspace__rail">{chat}</aside>}
          </div>
        </main>
      )}
    </div>
  );
}

export default function AppWithErrorBoundary() {
  return <AppErrorBoundary><ContractReview /></AppErrorBoundary>;
}

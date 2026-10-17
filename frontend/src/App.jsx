import { Component, useEffect, useMemo, useState } from "react";

const API_URL = "/documents/classify/stream";

function RiskBadge({ status }) {
  const label = status === "POTENTIAL_RISK"
    ? "POTENTIAL RISK · REVIEW"
    : status === "NO_RISK" ? "NO RISK FOUND"
      : status === "INSUFFICIENT_EVIDENCE" ? "UNRESOLVED"
        : (status || "NOT ANALYZED");
  const cls = status === "POTENTIAL_RISK"
    ? "risk-badge risk-badge--risk"
    : status === "NO_RISK" ? "risk-badge risk-badge--clear" : "risk-badge risk-badge--unsupported";
  return <span className={cls}>{label}</span>;
}

function RiskCard({ finding }) {
  const confidence = finding.confidence == null
    ? "Not calibrated"
    : Math.round(finding.confidence * 100) + "%";
  const supportScore = finding.raw_support_score == null
    ? "Not available"
    : Number(finding.raw_support_score).toFixed(2);
  const ruleMetadata = finding.provenance?.rule_registry_metadata || {};

  return (
    <article className="risk-card">
      <div className="risk-card__header">
        <div>
          <div className="eyebrow">{finding.scope || "clause"} · {finding.check_id}</div>
          <h3>{finding.risk_type || finding.question || "Risk review item"}</h3>
        </div>
        <RiskBadge status={finding.risk_status} />
      </div>

      <div className="risk-grid">
        <div><span className="field-label">Finding clause</span><strong>{finding.clause_id ?? "—"}</strong></div>
        {finding.evidence_clause_index != null && (
          <div>
            <span className="field-label">Evidence source clause</span>
            <strong>{finding.evidence_clause_index}</strong>
            <span className="field-note">{finding.evidence_scope === "related_contract_clause" ? "Retrieved from another clause in this contract" : "Quote from this clause"}</span>
          </div>
        )}
        {finding.evidence_source_status && (
          <div>
            <span className="field-label">Evidence verification</span>
            <strong>{finding.evidence_source_status}</strong>
            {finding.evidence_source_status !== "VERIFIED" && finding.evidence_clause_candidates?.length > 0 && (
              <span className="field-note">Possible source clauses: {finding.evidence_clause_candidates.join(", ")}</span>
            )}
          </div>
        )}
        <div>
          <span className="field-label">Confidence in prediction correctness</span>
          <strong>{confidence}</strong>
          <span className="field-note">{finding.confidence_status || "UNCALIBRATED"}</span>
        </div>
        <div>
          <span className="field-label">Support signal (not a probability)</span>
          <strong>{supportScore}</strong>
          <span className="field-note">Uncalibrated diagnostic from answer support, evidence, and model agreement.</span>
        </div>
        <div>
          <span className="field-label">Rule governance</span>
          <strong>{ruleMetadata.validation_status || finding.ground_truth_status || "PLAYBOOK_DERIVED"}</strong>
          <span className="field-note">{ruleMetadata.execution_status || "Review trigger only; not a legal conclusion."}</span>
          {ruleMetadata.jurisdiction_review_required && (
            <span className="field-note">Jurisdiction/applicability requires reviewer verification.</span>
          )}
        </div>
      </div>

      {finding.why_flagged && <div className="risk-detail"><strong>Why flagged:</strong> {finding.why_flagged}</div>}
      {finding.evidence && (
        <div className="evidence-quote">
          <strong>Exact contract evidence</strong>
          {Array.isArray(finding.evidence) ? (
            finding.evidence.map((item, index) => (
              <blockquote key={index}>Clause {item.clause_id}: “{item.quote}”</blockquote>
            ))
          ) : (
            <blockquote>“{finding.evidence}”</blockquote>
          )}
        </div>
      )}

      <div className="provenance-row">
        <span>Check: {finding.check_id || "—"}</span>
        {finding.provenance?.model && <span>Model: {finding.provenance.model}</span>}
        {finding.provenance?.agreement != null && (
          <span>Self-consistency: {Math.round(finding.provenance.agreement * 100)}%</span>
        )}
        {finding.provenance?.playbook_hash && (
          <span>Playbook: {finding.provenance.playbook_hash.slice(0, 12)}…</span>
        )}
      </div>

      {finding.supporting_sources?.length > 0 && (
        <details>
          <summary>Supporting sources</summary>
          <ul className="evidence-list">
            {finding.supporting_sources.map((source, index) => {
              const title = source.source_title || source.source_name || source.citation || source.title || "";
              const url = source.source_url || source.url;
              const note = source.supporting_quote_or_paraphrase;
              return (
                <li key={String(source.id || url || "source") + index}>
                  <strong>{source.id || source.name || "Source"}</strong> {title}
                  {note && note !== title && <> — {note}</>}
                  {url && <> — <a href={url} target="_blank" rel="noreferrer">source</a></>}
                  <div className="field-note">
                    Tier {source.source_tier || "unknown"} · {source.authority_status || "authority status unknown"} · Jurisdiction: {source.jurisdiction || "unspecified"}
                  </div>
                  <div className="field-note">
                    Citation: {source.pinpoint_citation || source.citation_status || "pinpoint not recorded"} · Effective date: {source.effective_date || source.effective_date_status || "not recorded"} · Licence: {source.license_status || "not checked"}
                  </div>
                </li>
              );
            })}
          </ul>
        </details>
      )}
    </article>
  );
}

class AppErrorBoundary extends Component {
  state = { error: null };
  static getDerivedStateFromError(error) { return { error }; }

  render() {
    if (this.state.error) {
      return (
        <main className="page">
          <h1>Contract Risk Review</h1>
          <div className="error">The interface failed to render. Refresh and retry.</div>
        </main>
      );
    }
    return this.props.children;
  }
}

function ContractReview() {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [trace, setTrace] = useState([]);
  const [tab, setTab] = useState("overview");
  const [riskFilter, setRiskFilter] = useState("all");
  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] = useState([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [chatError, setChatError] = useState(null);
  const [phase2Metrics, setPhase2Metrics] = useState(null);
  const [demoNotice, setDemoNotice] = useState(null);
  const [apiStatus, setApiStatus] = useState("checking");

  useEffect(() => {
    let cancelled = false;
    fetch("/health")
      .then((response) => response.ok ? response.json() : Promise.reject(new Error("API unavailable")))
      .then((data) => { if (!cancelled) setApiStatus(data.status === "ok" ? "online" : "degraded"); })
      .catch(() => { if (!cancelled) setApiStatus("offline"); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetch("/query/phase2-metrics")
      .then((response) => response.ok ? response.json() : Promise.reject(new Error("Metrics unavailable")))
      .then((data) => { if (!cancelled) setPhase2Metrics(data); })
      .catch(() => { if (!cancelled) setPhase2Metrics(null); });
    return () => { cancelled = true; };
  }, []);

  async function loadSavedDemo() {
    setError(null);
    setChatError(null);
    setDemoNotice(null);
    setChatMessages([]);
    setTrace([]);
    try {
      const response = await fetch("/query/demo-analysis");
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "The saved demo analysis is unavailable.");
      setResult(data);
      setDemoNotice(data.notice || "Loaded a saved synthetic demo.");
      setTab("overview");
      setRiskFilter("all");
    } catch (err) {
      setError(err.message || "Could not load the saved demo.");
    }
  }

  async function askContract(questionOverride) {
    const question = String(questionOverride ?? chatInput).trim();
    if (!result?.analysis_id || !question || chatLoading) return;
    setChatMessages((messages) => [...messages, { role: "user", text: question }]);
    setChatInput("");
    setChatError(null);
    setChatLoading(true);
    try {
      const response = await fetch("/query/contract", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          analysis_id: result.analysis_id,
          question,
          history: chatMessages.slice(-8).map((message) => ({
            role: message.role,
            content: message.role === "user" ? message.text : (message.answer || ""),
          })).filter((message) => message.content.trim()),
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || ("Assistant request failed (" + response.status + ")"));
      setChatMessages((messages) => [...messages, { role: "assistant", ...data }]);
    } catch (err) {
      setChatError(err.message || "The contract assistant could not answer this question.");
    } finally {
      setChatLoading(false);
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (!file) return;

    setLoading(true);
    setError(null);
    setResult(null);
    setDemoNotice(null);
    setTrace([]);
    setChatMessages([]);
    setChatError(null);
    setTab("overview");

    try {
      const formData = new FormData();
      formData.append("file", file);
      const response = await fetch(API_URL, { method: "POST", body: formData });

      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || ("Request failed (" + response.status + ")"));
      }
      if (!response.body) throw new Error("The server did not provide a progress stream.");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let receivedResult = false;

      const handleEvent = (raw) => {
        const line = raw.split("\n").find((item) => item.startsWith("data:"));
        if (!line) return;
        const event = JSON.parse(line.slice(5).trim());
        if (event.type === "progress") {
          setTrace((items) => [...items, event]);
        } else if (event.type === "result") {
          setResult(event.data);
          receivedResult = true;
        } else if (event.type === "error") {
          throw new Error(event.message || "Analysis failed.");
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
      if (!receivedResult) throw new Error("The analysis stream ended without a result.");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const assessment = result?.contract_risk_assessment || {};
  const clauses = result?.clauses || [];
  const risks = useMemo(
    () => clauses.flatMap((clause) =>
      (clause.risk_findings || []).map((finding) => ({
        ...finding,
        clause_id: clause.clause_index,
        clause_type: clause.predicted_label,
        clause_text: clause.clause_text,
      }))
    ),
    [clauses]
  );
  const contractWideRisks = [
    ...(assessment.cross_clause_findings || []),
    ...(assessment.document_findings || []),
  ].map((finding) => ({ ...finding, clause_id: (finding.clause_ids || []).join(" + "), scope: finding.scope || "contract" }));
  const allRisks = [...risks, ...contractWideRisks];
  const potential = allRisks.filter((item) => item.risk_status === "POTENTIAL_RISK");
  const uncertain = allRisks.filter((item) => item.risk_status === "INSUFFICIENT_EVIDENCE");
  const visibleRisks = riskFilter === "potential"
    ? potential
    : riskFilter === "uncertain" ? uncertain : allRisks;

  return (
    <main className="page">
      <header className="app-bar">
        <div className="brand-lockup">
          <div className="brand-mark" aria-hidden="true"><span>C</span><i /></div>
          <div><strong>Clausewise</strong><span>CONTRACT INTELLIGENCE</span></div>
        </div>
        <div className="app-bar__right">
          <span className={"system-status system-status--" + apiStatus}>
            <i /> {apiStatus === "online" ? "API connected" : apiStatus === "checking" ? "Checking workspace" : apiStatus === "degraded" ? "API needs attention" : "API offline"}
          </span>
          <span className="workspace-tag">PHASE 2 WORKSPACE</span>
        </div>
      </header>

      <header className="hero">
        <div className="hero-copy">
          <div className="eyebrow">AI-assisted review · evidence-first workflow</div>
          <h1>Know what your contract says. See why it matters.</h1>
          <p>Classify clauses, surface commercial review triggers, inspect exact wording, and ask grounded questions about the agreement—all in one auditable workspace.</p>
          <div className="hero-points">
            <span><i /> Exact-text evidence</span>
            <span><i /> Cross-clause review</span>
            <span><i /> Traceable findings</span>
          </div>
        </div>
        <div className="hero-side">
          <div className="hero-orbit" aria-hidden="true"><span>§</span><i /><b /></div>
          <div className="hero-side__caption">REVIEW WITH CONTEXT<br /><strong>Not just a risk score.</strong></div>
          {result?.demo_mode && <span className="demo-mode-pill">SYNTHETIC DEMO</span>}
          {result?.analysis_id && (
            <div className="analysis-id"><span>Analysis ID</span><code>{result.analysis_id}</code></div>
          )}
        </div>
      </header>

      <section className="intake-panel" aria-label="Start contract review">
        <div className="intake-heading">
          <div><span className="step-tag">01 / START HERE</span><h2>Review a contract</h2></div>
          <span className="intake-note">PDF or plain text · analysis results stay linked to this workspace</span>
        </div>
        <form className="upload-form" onSubmit={handleSubmit}>
          <label className="file-picker">
            <span className="file-picker__icon" aria-hidden="true">↑</span>
            <span className="file-picker__copy"><strong>{file ? file.name : "Choose a contract file"}</strong><small>{file ? (file.size / 1024).toFixed(1) + " KB · ready to analyze" : "Select a PDF or TXT document from your computer"}</small></span>
            <span className="file-picker__button">Browse files</span>
            <input type="file" accept=".pdf,.txt" onChange={(e) => setFile(e.target.files?.[0] || null)} disabled={loading} />
          </label>
          <div className="upload-actions">
            <button type="submit" disabled={!file || loading}>{loading ? "Analyzing contract…" : "Analyze contract"} <span aria-hidden="true">→</span></button>
            <button type="button" className="button-secondary" onClick={loadSavedDemo} disabled={loading}>Open guided demo</button>
            <a className="sample-link" href="/query/demo-contract" download>Download sample agreement ↗</a>
          </div>
        </form>
        <p className="privacy-note" role="note"><span aria-hidden="true">ⓘ</span> Privacy: inference runs locally, but clause text is sent to the configured Cohere embedding API. Do not upload confidential documents unless that transfer is authorized; this build is not fully offline.</p>
      </section>

      {!result && !loading && (
        <section className="welcome-grid" aria-label="How the workspace works">
          <article className="welcome-card welcome-card--primary">
            <span className="step-tag">02 / INSPECT</span><div className="welcome-icon">⌕</div>
            <h3>Evidence before conclusions</h3>
            <p>Every displayed risk candidate points back to contract wording. Unverified interpretations should remain unresolved—not become confident legal claims.</p>
          </article>
          <article className="welcome-card">
            <span className="step-tag">03 / ASK</span><div className="welcome-icon">↗</div>
            <h3>Ask the contract</h3>
            <p>Explore termination, liability, payment, IP ownership, and interactions between clauses with source-backed answers and explicit uncertainty.</p>
          </article>
          <article className="welcome-card">
            <span className="step-tag">BUILT FOR REVIEW</span><div className="welcome-icon">◎</div>
            <h3>Auditable by design</h3>
            <p>Inspect rule status, evidence provenance, and downloadable artifacts. A passed software check is never presented as proof of legal accuracy.</p>
          </article>
        </section>
      )}

      {demoNotice && <p className="demo-notice" role="status">{demoNotice}</p>}
      {error && <div className="error" role="alert">{error}</div>}

      <details className="experiment-snapshot">
        <summary>Technical validation snapshot <span className="snapshot-hint">Open to inspect runtime metrics</span></summary>
        <div className="experiment-snapshot__body">
          <div className="experiment-metrics">
            <div><strong>{phase2Metrics?.playbook?.deterministic_rule_count ?? "—"}</strong><span>Executable playbook rules</span></div>
            <div><strong>{phase2Metrics?.playbook?.clause_question_count ?? "—"}</strong><span>Clause-level playbook questions</span></div>
            <div><strong>{phase2Metrics?.playbook?.cross_clause_question_count ?? "—"}</strong><span>Cross-clause questions</span></div>
            <div><strong>{phase2Metrics?.playbook?.document_question_count ?? "—"}</strong><span>Document-level questions</span></div>
            <div><strong>{phase2Metrics?.rule_validation?.status || "NOT_RUN"}</strong><span>Rule configuration / taxonomy validation</span></div>
            <div><strong>{phase2Metrics?.classification_index_isolation?.status || "NOT_RUN"}</strong><span>Separate CUAD classifier-index isolation</span></div>
            <div><strong>{phase2Metrics?.release_validation?.status || "NOT_RUN"}</strong><span>Full release validation</span></div>
            <div><strong>{phase2Metrics?.playbook?.taxonomy_domain_count ?? "—"}</strong><span>Canonical risk domains</span></div>
          </div>
          <p>
            {phase2Metrics ? "Playbook v" + (phase2Metrics.playbook?.source_version || "—") + ". Rule tests and release reports are shown as NOT_RUN until their source scripts execute." : "Could not load the saved Phase 2 configuration and conformance reports."}
          </p>
          <p>
            {phase2Metrics?.separate_cuad_category_baseline?.accuracy == null
              ? "The separate CUAD clause-category retrieval baseline has not been loaded."
              : "Separate CUAD category baseline: " + (phase2Metrics.separate_cuad_category_baseline.accuracy * 100).toFixed(1) + "% accuracy and " + (phase2Metrics.separate_cuad_category_baseline.macro_f1 * 100).toFixed(1) + "% macro-F1 across " + (phase2Metrics.separate_cuad_category_baseline.test_clauses ?? "—") + " held-out clauses. These are clause-category metrics, not risk accuracy."}
          </p>
          <p><strong>Interpretation:</strong> direct rule hits are review triggers with exact contract quotes. The release reports conformance, rule integrity and evidence provenance—not legal-risk accuracy, enforceability or calibrated probability. A rule miss is not proof that a contract is safe.</p>
          <p><a href="/query/phase2-metrics" target="_blank" rel="noreferrer">Open metrics JSON</a></p>
        </div>
      </details>

      {loading && (
        <section className="trace" aria-live="polite">
          <div className="trace-header"><h2>Live analysis trace</h2><span>Running</span></div>
          <ol className="trace-list">
            {trace.map((event, index) => (
              <li key={String(event.stage) + index} className="trace-item">
                <span className="trace-stage">{String(event.stage).replaceAll("_", " ")}</span>
                <span>{event.message}</span>
              </li>
            ))}
          </ol>
        </section>
      )}

      {result && (
        <>
          <section className="metadata-card">
            <div>
              <div className="eyebrow">Contract profile</div>
              <h2>{result.contract_metadata?.name || result.filename}</h2>
              <p className="muted">{result.filename}</p>
            </div>
            <div className="metric-strip">
              <div><span>Clauses</span><strong>{result.total_clauses}</strong></div>
              <div><span>Potential risks</span><strong>{potential.length}</strong></div>
              <div><span>Unresolved</span><strong>{uncertain.length}</strong></div>
              <div><span>Calibration</span><strong>{assessment.confidence_status || "UNCALIBRATED"}</strong></div>
            </div>
            <div className="metadata-grid">
              <div><span>Parties</span><strong>{result.contract_metadata?.parties?.join(" · ") || "Not extracted"}</strong></div>
              <div><span>Agreement date</span><strong>{result.contract_metadata?.agreement_date || "Not extracted"}</strong></div>
              <div><span>Effective date</span><strong>{result.contract_metadata?.effective_date || "Not extracted"}</strong></div>
              <div><span>Expiration date</span><strong>{result.contract_metadata?.expiration_date || "Not extracted"}</strong></div>
              <div><span>Governing law</span><strong>{result.contract_metadata?.governing_law || "Not extracted"}</strong></div>
              <div><span>Risk source</span><strong>{assessment.gold_status === "PLAYBOOK_DERIVED" ? "Playbook-derived" : (assessment.gold_status || "Playbook-derived")}</strong></div>
            </div>
          </section>

          <nav className="tabs">
            <button type="button" className={tab === "overview" ? "tab tab--active" : "tab"} onClick={() => setTab("overview")}>Overview</button>
            <button type="button" className={tab === "clauses" ? "tab tab--active" : "tab"} onClick={() => setTab("clauses")}>Clauses</button>
            <button type="button" className={tab === "risks" ? "tab tab--active" : "tab"} onClick={() => setTab("risks")}>Risks ({potential.length})</button>
            <button type="button" className={tab === "chat" ? "tab tab--active" : "tab"} onClick={() => setTab("chat")}>Ask this contract</button>
          </nav>

          {tab === "overview" && (
            <section className="overview-grid">
              <article className="panel panel--accent">
                <div className="eyebrow">Contract-level result</div>
                <h2>{assessment.status === "POTENTIAL_RISK" ? "Potential risk identified" : (assessment.status || "Assessment unavailable")}</h2>
                <p>{assessment.reason}</p>
                <div className="status-line">
                  <span>Review status: {assessment.status || "Not available"}</span>
                  <span>Contract-level confidence: not estimated</span>
                </div>
                <p className="muted">Clause-level confidence is shown only after adjudicated calibration. No ordinal severity labels or aggregate contract probability are used.</p>
                <p className="muted">Policy: {assessment.rule_registry?.status || "PILOT_REVIEW_ONLY"} · Source citations: {assessment.rule_registry?.source_citation_status || "incomplete"} · Findings: {assessment.gold_status || "PLAYBOOK_DERIVED"}.</p>
              </article>

              <article className="panel">
                <div className="eyebrow">Audit artifacts</div>
                <h2>Downloads</h2>
                <div className="download-list">
                  {Object.entries(result.downloads || {}).map(([key, url]) => (
                    <a key={key} href={url} download>{String(key).replaceAll("_", " ")}</a>
                  ))}
                </div>
              </article>

              <article className="panel">
                <div className="eyebrow">Risk snapshot</div>
                <h2>{potential.length} evidence-supported checks</h2>
                <p>{uncertain.length} checks remain unresolved and should not be treated as no-risk.</p>
              </article>
            </section>
          )}

          {tab === "clauses" && (
            <section className="results">
              <div className="section-heading"><div><div className="eyebrow">Clause-by-clause</div><h2>{clauses.length} extracted segments</h2></div></div>
              <div className="clause-list">
                {clauses.map((clause) => (
                  <article key={clause.clause_index} className="clause-card">
                    <div className="clause-card__header">
                      <div><span className="field-label">Clause {clause.clause_index}</span><h3>{clause.predicted_label || "No applicable label"}</h3></div>
                      <RiskBadge status={clause.risk_status} />
                    </div>
                    <p className="clause-text">{clause.clause_text}</p>
                    <div className="classification-row">
                      <span>CUAD status: <strong>{clause.classification_status}</strong></span>
                      <span>Classification confidence: <strong>{clause.classification_confidence == null ? "not calibrated" : Math.round(clause.classification_confidence * 100) + "%"}</strong></span>
                    </div>
                    {clause.risk_findings?.filter((finding) => finding.risk_status !== "NO_RISK").map((finding, index) => (
                      <RiskCard key={String(clause.clause_index) + "-" + String(finding.check_id || index)} finding={finding} />
                    ))}
                  </article>
                ))}
              </div>
            </section>
          )}

          {tab === "risks" && (
            <section className="results">
              <div className="section-heading">
                <div><div className="eyebrow">Risk-only review</div><h2>Inspect the flags without reading every clause</h2></div>
                <div className="filter-row">
                  {["all", "potential", "uncertain"].map((value) => (
                    <button key={value} type="button" className={riskFilter === value ? "filter-button filter-button--active" : "filter-button"} onClick={() => setRiskFilter(value)}>
                      {value === "all" ? "All" : value === "potential" ? "Potential" : "Uncertain"}
                    </button>
                  ))}
                </div>
              </div>
              <div className="risk-stack">
                {visibleRisks.map((finding, index) => (
                  <RiskCard key={String(finding.clause_id) + "-" + String(finding.check_id || index)} finding={finding} />
                ))}
                {!visibleRisks.length && <div className="panel"><h3>No findings in this view.</h3></div>}
              </div>
              {(assessment.deterministic_cross_checks || []).length > 0 && (
                <section className="results">
                  <div className="section-heading">
                    <div><div className="eyebrow">Rule-based review candidates</div><h2>Deterministic interaction signals</h2></div>
                  </div>
                  <p className="muted">These are conservative candidate signals, not model-verified risk findings or legal conclusions. Review the quoted contract provisions before acting on them.</p>
                  <div className="risk-stack">
                    {assessment.deterministic_cross_checks.map((signal) => (
                      <article className="panel" key={signal.id}>
                        <div className="clause-card__header">
                          <div><div className="eyebrow">{signal.id} · {signal.name?.replaceAll("_", " ")}</div><h3>Review candidate</h3></div>
                          <span className="risk-badge risk-badge--unsupported">REVIEW</span>
                        </div>
                        <p>{signal.reason}</p>
                        {signal.evidence?.length > 0 && (
                          <div className="evidence-quote">
                            <strong>Source clauses</strong>
                            {signal.evidence.map((item, index) => (
                              <blockquote key={signal.id + "-" + index}>Clause {item.clause_id}: “{item.quote}”</blockquote>
                            ))}
                          </div>
                        )}
                      </article>
                    ))}
                  </div>
                </section>
              )}
            </section>
          )}

          {tab === "chat" && (
            <section className="contract-chat">
              <div className="chat-heading">
                <div>
                  <div className="eyebrow">Contract-aware assistant</div>
                  <h2>Ask questions about {result.contract_metadata?.name || result.filename}</h2>
                  <p className="muted">Answers are grounded in this analysis. Each material contract claim should cite exact wording; if the source does not support an answer, the assistant should say so rather than guess.</p>
                </div>
                <span className="chat-model">{chatMessages.some((message) => message.model === "EXTRACTIVE_FALLBACK") ? "Source-only fallback" : "Contract-linked assistant"}</span>
              </div>

              <div className="suggested-questions" aria-label="Suggested questions">
                {[
                  "Summarize the main obligations in plain English.",
                  "What are the termination rights and notice periods?",
                  "What liability limits or exceptions should I review?",
                  "Who owns the intellectual property created under this agreement?",
                  "Which findings still need more evidence?",
                ].map((question) => (
                  <button key={question} type="button" onClick={() => askContract(question)} disabled={chatLoading}>{question}</button>
                ))}
              </div>

              <div className="chat-messages" aria-live="polite" aria-label="Conversation">
                {!chatMessages.length && (
                  <div className="chat-empty">
                    <strong>Ask a question or choose a suggested prompt.</strong>
                    <span>Try a plain-language explanation, a comparison of clauses, or ask what exact wording triggered a playbook rule.</span>
                  </div>
                )}
                {chatMessages.map((message, index) => (
                  <article key={String(message.role) + index} className={message.role === "user" ? "chat-message chat-message--user" : "chat-message chat-message--assistant"}>
                    <div className="chat-message__role">{message.role === "user" ? "You" : "Contract assistant"}{message.insufficient_evidence ? " · evidence limited" : ""}</div>
                    <p>{message.role === "user" ? message.text : message.answer}</p>
                    {message.citations?.length > 0 && (
                      <div className="chat-citations">
                        <strong>Verified contract evidence</strong>
                        {message.citations.map((citation, citationIndex) => (
                          <blockquote key={String(citation.clause_index) + citationIndex}>
                            <span>Clause {citation.clause_index}{citation.reason ? " · " + citation.reason : ""}</span>
                            “{citation.quote}”
                          </blockquote>
                        ))}
                      </div>
                    )}
                    {message.role === "assistant" && message.disclaimer && <span className="chat-disclaimer">{message.disclaimer}</span>}
                    {message.follow_up_questions?.length > 0 && (
                      <div className="chat-followups">
                        {message.follow_up_questions.map((question) => <button key={question} type="button" onClick={() => askContract(question)} disabled={chatLoading}>{question}</button>)}
                      </div>
                    )}
                  </article>
                ))}
                {chatLoading && <div className="chat-thinking"><span className="chat-thinking__dot" /> Checking the relevant contract clauses…</div>}
              </div>

              {chatError && <div className="error" role="alert">{chatError}</div>}
              <form className="chat-composer" onSubmit={(event) => { event.preventDefault(); askContract(); }}>
                <textarea value={chatInput} onChange={(event) => setChatInput(event.target.value)} placeholder="Ask something specific about this contract…" rows={3} maxLength={1200} disabled={chatLoading} aria-label="Question about this contract" />
                <button type="submit" disabled={chatLoading || !chatInput.trim()}>{chatLoading ? "Thinking…" : "Ask question"}</button>
              </form>
              <p className="chat-safety-note">AI-assisted review only, not legal advice. The model may still misinterpret a clause. Risk findings are review triggers, not calibrated probabilities.</p>
            </section>
          )}
        </>
      )}
    </main>
  );
}

export default function AppWithErrorBoundary() {
  return <AppErrorBoundary><ContractReview /></AppErrorBoundary>;
}

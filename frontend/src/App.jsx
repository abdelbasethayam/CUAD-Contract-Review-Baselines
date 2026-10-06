import { Component, useMemo, useState } from "react";

const API_URL = "/documents/classify/stream";

function RiskBadge({ status, level }) {
  const label = status === "POTENTIAL_RISK"
    ? (level || "POTENTIAL RISK")
    : status === "NO_RISK" ? "NO RISK" : (status || "NOT ANALYZED");
  const cls = status === "POTENTIAL_RISK"
    ? "risk-badge risk-badge--risk"
    : status === "NO_RISK" ? "risk-badge risk-badge--clear" : "risk-badge risk-badge--unsupported";
  return <span className={cls}>{label}</span>;
}

function RiskCard({ finding }) {
  const confidence = finding.confidence == null
    ? "Uncalibrated"
    : Math.round(finding.confidence * 100) + "%";

  return (
    <article className="risk-card">
      <div className="risk-card__header">
        <div>
          <div className="eyebrow">{finding.scope || "clause"} · {finding.check_id}</div>
          <h3>{finding.risk_type || finding.question || "Risk review item"}</h3>
        </div>
        <RiskBadge status={finding.risk_status} level={finding.risk_level} />
      </div>

      <div className="risk-grid">
        <div><span className="field-label">Clause</span><strong>{finding.clause_id ?? "—"}</strong></div>
        <div>
          <span className="field-label">Confidence</span>
          <strong>{confidence}</strong>
          <span className="field-note">{finding.confidence_status || "UNCALIBRATED"}</span>
        </div>
        <div>
          <span className="field-label">Triage score</span>
          <strong>{finding.final_score == null ? "Not scored" : String(finding.final_score) + " / 20"}</strong>
          <span className="field-note">Internal review-prioritization score</span>
        </div>
        <div>
          <span className="field-label">Ground truth / provenance</span>
          <strong>{finding.ground_truth_status || "NOT_AVAILABLE"}</strong>
          <span className="field-note">Not gold unless manually adjudicated.</span>
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
        {finding.review_escalation && <span>Escalation: {finding.review_escalation}</span>}
        {finding.human_review_status && <span>Review: {finding.human_review_status}</span>}
        {finding.source_tier && <span>Source tier: {finding.source_tier}</span>}
        {finding.provenance?.playbook_hash && (
          <span>Playbook: {finding.provenance.playbook_hash.slice(0, 12)}…</span>
        )}
      </div>

      {finding.supporting_sources?.length > 0 && (
        <details>
          <summary>Supporting sources</summary>
          <ul className="evidence-list">
            {finding.supporting_sources.map((source, index) => (
              <li key={String(source.id || source.url || "source") + index}>
                <strong>{source.id || source.name || "Source"}</strong> {source.citation || source.title || ""}
                {source.url && <> — <a href={source.url} target="_blank" rel="noreferrer">source</a></>}
              </li>
            ))}
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

  async function handleSubmit(event) {
    event.preventDefault();
    if (!file) return;

    setLoading(true);
    setError(null);
    setResult(null);
    setTrace([]);
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
      <header className="hero">
        <div>
          <div className="eyebrow">CUAD Contract Review · Phase 1 + Phase 2</div>
          <h1>Evidence-grounded contract risk review.</h1>
          <p>Upload a contract to segment and classify clauses, then inspect risk findings with exact evidence and reproducible provenance.</p>
        </div>
        {result?.analysis_id && (
          <div className="analysis-id"><span>Analysis ID</span><code>{result.analysis_id}</code></div>
        )}
      </header>

      <form className="upload-form" onSubmit={handleSubmit}>
        <input type="file" accept=".pdf,.txt" onChange={(e) => setFile(e.target.files?.[0] || null)} disabled={loading} />
        <button type="submit" disabled={!file || loading}>{loading ? "Analyzing…" : "Analyze contract"}</button>
      </form>

      {error && <div className="error">{error}</div>}

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
              <div><span>Contract type</span><strong>{result.contract_metadata?.contract_type || "Not determined"}</strong></div>
              <div><span>Ground truth</span><strong>{assessment.gold_status || "PLAYBOOK_DERIVED"}</strong></div>
            </div>
          </section>

          <nav className="tabs">
            <button type="button" className={tab === "overview" ? "tab tab--active" : "tab"} onClick={() => setTab("overview")}>Overview</button>
            <button type="button" className={tab === "clauses" ? "tab tab--active" : "tab"} onClick={() => setTab("clauses")}>Clauses</button>
            <button type="button" className={tab === "risks" ? "tab tab--active" : "tab"} onClick={() => setTab("risks")}>Risks ({potential.length})</button>
          </nav>

          {tab === "overview" && (
            <section className="overview-grid">
              <article className="panel panel--accent">
                <div className="eyebrow">Contract-level result</div>
                <h2>{assessment.status === "POTENTIAL_RISK" ? "Potential risk identified" : (assessment.status || "Assessment unavailable")}</h2>
                <p>{assessment.reason}</p>
                <div className="status-line">
                  <span>Overall severity: {assessment.overall_severity || assessment.overall_risk || "Not scored"}</span>
                  <span>Triage score: {assessment.overall_score == null ? "Not scored" : String(assessment.overall_score) + " / 20"}</span>
                  <span>Confidence: {assessment.overall_confidence == null ? "Not calibrated" : Math.round(assessment.overall_confidence * 100) + "%"}</span>
                </div>
                <div className="status-line">
                  {assessment.legal_review_required && <span>Legal review required</span>}
                  {assessment.business_owner_review_required && <span>Business-owner review</span>}
                  {assessment.privacy_security_review_required && <span>Privacy/security review</span>}
                </div>
                <p className="muted">This uploaded contract has no independent gold label. Findings are tagged {assessment.gold_status || "PLAYBOOK_DERIVED"}.</p>
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
                      <RiskBadge status={clause.risk_status} level={clause.risk_level} />
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

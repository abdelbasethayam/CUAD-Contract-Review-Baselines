import { Component, useState } from "react";

const API_URL = "/documents/classify/stream";

class AppErrorBoundary extends Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <main className="page">
          <h1>Contract Clause Classifier</h1>
          <div className="error" role="alert">
            The interface failed to render. Refresh the page and try again.
            <details>
              <summary>Technical details</summary>
              <pre>{this.state.error.message}</pre>
            </details>
          </div>
        </main>
      );
    }
    return this.props.children;
  }
}

function ContractClassifier() {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [trace, setTrace] = useState([]);

  function handleFileChange(e) {
    setFile(e.target.files[0] || null);
    setResult(null);
    setError(null);
    setTrace([]);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!file) return;

    setLoading(true);
    setError(null);
    setResult(null);
    setTrace([]);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch(API_URL, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || `Request failed (${response.status})`);
      }

      if (!response.body) {
        throw new Error("The server did not provide a progress stream.");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let receivedResult = false;

      const handleEvent = (rawEvent) => {
        const dataLine = rawEvent
          .split("\n")
          .find((line) => line.startsWith("data:"));
        if (!dataLine) return;

        const event = JSON.parse(dataLine.slice(5).trim());
        if (event.type === "progress") {
          setTrace((items) => [...items, event]);
        } else if (event.type === "result") {
          if (!event.data || !Array.isArray(event.data.clauses)) {
            throw new Error("The server returned an invalid classification response.");
          }
          setResult(event.data);
          receivedResult = true;
        } else if (event.type === "error") {
          setTrace((items) => [
            ...items,
            { stage: "error", message: event.message || "Classification failed." },
          ]);
          throw new Error(event.message || "Classification failed.");
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
      if (!receivedResult) throw new Error("The classification stream ended without a result.");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const assessment = result?.contract_risk_assessment || {};

  return (
    <div className="page">
      <header className="header">
        <h1>Contract Clause Classifier</h1>
        <p>Upload a contract (PDF or .txt). Each clause gets a CUAD label.</p>
      </header>

      <form className="upload-form" onSubmit={handleSubmit}>
        <input
          type="file"
          accept=".pdf,.txt"
          onChange={handleFileChange}
          disabled={loading}
        />
        <button type="submit" disabled={!file || loading}>
          {loading ? "Classifying..." : "Classify contract"}
        </button>
      </form>

      {error && <div className="error">{error}</div>}

      {loading && (
        <p className="status">
          Analysis is running. The live trace below shows the current pipeline stage.
        </p>
      )}

      {trace.length > 0 && (
        <section className="trace" aria-live="polite" aria-label="Analysis trace">
          <div className="trace-header">
            <h2>Live analysis trace</h2>
            <span>{loading ? "Running" : error ? "Failed" : "Finished"}</span>
          </div>
          <ol className="trace-list">
            {trace.map((event, index) => (
              <li key={`${event.stage}-${index}`} className={`trace-item trace-item--${event.stage}`}>
                <span className="trace-stage">{event.stage.replaceAll("_", " ")}</span>
                <span>{event.message}</span>
              </li>
            ))}
          </ol>
        </section>
      )}

      {result && (
        <>
        <section className="contract-risk-assessment">
          <h2>Contract Risk Assessment</h2>
          <div className="summary" aria-label="Contract risk assessment summary">
            <span>Overall Risk: {assessment.overall_risk || "Unavailable"}</span>
            <span>Status: {assessment.status || "RISK_ANALYSIS_UNAVAILABLE"}</span>
          </div>
          {assessment.summary && (
            <div className="risk-detail"><strong>Summary:</strong> {assessment.summary}</div>
          )}
          {assessment.risk_domains?.length > 0 && (
            <div className="risk-detail">
              <strong>Risk Domains</strong>
              <ul className="evidence-list">
                {assessment.risk_domains.map((domain, index) => (
                  <li key={`${domain.domain}-${index}`}>
                    <strong>{domain.domain}</strong> — {domain.severity}: {domain.title}
                    <div>{domain.description}</div>
                    <div><strong>Impact:</strong> {domain.impact}</div>
                    <div><strong>Recommendation:</strong> {domain.recommendation}</div>
                    {domain.evidence?.map((item, evidenceIndex) => (
                      <div key={`${item.clause_id}-${evidenceIndex}`}><strong>Clause {item.clause_id}:</strong> {item.quote}</div>
                    ))}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {assessment.cross_clause_findings?.length > 0 && (
            <div className="risk-detail"><strong>Cross-Clause Risks</strong><ul className="evidence-list">
              {assessment.cross_clause_findings.map((finding, index) => <li key={index}>Clauses {(finding.clauses || []).join(" + ")} — {finding.severity}: {finding.finding}</li>)}
            </ul></div>
          )}
          {assessment.positive_protections?.length > 0 && (
            <div className="risk-detail"><strong>Positive Protections</strong><ul className="evidence-list">{assessment.positive_protections.map((item, index) => <li key={index}>{item}</li>)}</ul></div>
          )}
          {assessment.missing_protections?.length > 0 && (
            <div className="risk-detail"><strong>Missing Protections</strong><ul className="evidence-list">{assessment.missing_protections.map((item, index) => <li key={index}>{item}</li>)}</ul></div>
          )}
          {assessment.limitations?.length > 0 && (
            <div className="risk-detail"><strong>Limitations</strong><ul className="evidence-list">{assessment.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul></div>
          )}
        </section>
        <section className="results">
          <h2>
            CUAD Classification Evidence — {result.filename} - {result.total_clauses} clause
            {result.total_clauses === 1 ? "" : "s"}
          </h2>
          <div className="summary" aria-label="Risk analysis summary">
            <span>Total Clauses: {result.total_clauses}</span>
            <span>CUAD labels assigned: {result.clauses.filter((c) => c?.predicted_label !== "NO_APPLICABLE_LABEL").length}</span>
            <span>No applicable CUAD label: {result.clauses.filter((c) => c?.predicted_label === "NO_APPLICABLE_LABEL").length}</span>
          </div>

          <ul className="clause-list">
            {result.clauses.map((clause) => (
              <li key={clause.clause_index} className="clause-card">
                <h3>CUAD Classification</h3>
                <div className="clause-label">Final CUAD classification: {clause.clause_type || clause.predicted_label}</div>
                {Array.isArray(clause.candidate_labels) && clause.candidate_labels.length > 0 && (
                  <div className="risk-detail">
                    <strong>Candidate labels:</strong> {clause.candidate_labels.join(", ")}
                  </div>
                )}
                <details open={Array.isArray(clause.retrieved_examples) && clause.retrieved_examples.length > 0}>
                  <summary>CUAD Retrieval Evidence</summary>
                  <ul className="evidence-list">
                    {(clause.retrieved_examples || []).map((example, i) => (
                      <li key={`${example.source_id || example.label || example.clause_type || "evidence"}-${i}`}>
                        <strong>{example.label || example.clause_type}</strong> - score {example.score}
                        <div>{example.quote || example.clause_text}</div>
                      </li>
                    ))}
                    {(!clause.retrieved_examples || clause.retrieved_examples.length === 0) && <li>No CUAD retrieval evidence.</li>}
                  </ul>
                </details>
                <p className="clause-text">{clause.clause_text}</p>
              </li>
            ))}
          </ul>
        </section>
        </>
      )}
    </div>
  );
}

export default function AppWithErrorBoundary() {
  return (
    <AppErrorBoundary>
      <ContractClassifier />
    </AppErrorBoundary>
  );
}

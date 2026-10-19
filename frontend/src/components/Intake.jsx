import React, { useRef, useState } from "react";
import { appPath } from "../lib/api.js";

function Specimen() {
  return (
    <figure className="specimen" aria-label="Example of a flagged clause">
      <div className="specimen__sheet">
        <p className="specimen__ref">Clause 3 · Cap on liability</p>
        <p className="specimen__text">
          Supplier's aggregate liability under this Agreement is limited. Supplier's aggregate liability shall{" "}
          <mark className="specimen__mark">not exceed the fees paid by Customer in the previous one month.</mark>{" "}
          Customer's liability during the Term is capped at ten times the annual fees.
        </p>
      </div>
      <figcaption className="specimen__note">
        <strong>Liability and indemnity</strong>
        <span>The supplier's cap is one month of fees. The customer's is ten times fees. Check whether the gap is intended.</span>
      </figcaption>
    </figure>
  );
}

export default function Intake({ file, setFile, loading, demoLoading, restoring, onSubmit, onDemo }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const busy = loading || demoLoading;

  function pick(candidate) {
    if (!candidate) return;
    const ok = /\.(pdf|txt)$/i.test(candidate.name);
    if (ok) setFile(candidate);
  }

  return (
    <section className="landing" aria-label="Start a contract review">
      <div className="landing__copy">
        <h1>Find what matters in a contract, with the exact wording to back it up.</h1>
        <p className="landing__lede">
          Upload an agreement. Clausewise labels each clause, flags terms worth a second look, and answers your questions
          using the contract's own words.
        </p>

        <form className="intake" onSubmit={onSubmit}>
          <label
            className={"dropzone" + (dragging ? " dropzone--active" : "") + (file ? " dropzone--filled" : "")}
            onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => { event.preventDefault(); setDragging(false); pick(event.dataTransfer.files?.[0]); }}
          >
            <input
              ref={inputRef}
              type="file"
              accept=".pdf,.txt"
              disabled={busy}
              onChange={(event) => pick(event.target.files?.[0])}
            />
            <span className="dropzone__glyph" aria-hidden="true">{file ? "✓" : "↑"}</span>
            <span className="dropzone__copy">
              <strong>{file ? file.name : "Drop a contract here, or browse"}</strong>
              <small>{file ? (file.size / 1024).toFixed(0) + " KB, ready to analyse" : "PDF or plain text"}</small>
            </span>
          </label>

          <div className="intake__actions">
            <button type="submit" className="button button--primary" disabled={!file || busy}>
              {loading ? "Analysing…" : "Analyse contract"}
            </button>
            <button type="button" className="button button--quiet" onClick={onDemo} disabled={busy}>
              {demoLoading ? "Opening sample…" : "Explore a sample contract"}
            </button>
          </div>
        </form>

        <p className="landing__fineprint">
          Clause text is sent to the Cohere embedding service as part of the analysis. Don't upload confidential
          documents unless that transfer is authorised.
          {" "}<a href={appPath("query/demo-contract")} download>Download the sample</a>
        </p>
        {restoring && <p className="landing__restoring" role="status">Reopening your last analysis…</p>}
      </div>
      <Specimen />
    </section>
  );
}

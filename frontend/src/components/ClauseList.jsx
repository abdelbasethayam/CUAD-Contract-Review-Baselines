import React, { useEffect, useMemo, useRef, useState } from "react";
import { isUnclassified, plural } from "../lib/risk.js";

const CLAMP = 420;

function sentenceCase(value) {
  const text = String(value || "");
  const letters = text.replace(/[^A-Za-z]/g, "");
  if (letters.length < 4 || text !== text.toUpperCase()) return text;
  const lower = text.toLowerCase();
  return lower.charAt(0).toUpperCase() + lower.slice(1);
}

// Many contracts repeat the heading as the first line of the clause body.
function withoutHeading(text, heading) {
  const lines = String(text || "").split("\n");
  const first = (lines[0] || "").replace(/^\s*(\d+(\.\d+)*[.)]?\s*)/, "").trim().toLowerCase();
  const wanted = String(heading || "").replace(/^\s*(\d+(\.\d+)*[.)]?\s*)/, "").trim().toLowerCase();
  if (wanted && first === wanted && lines.length > 1) return lines.slice(1).join("\n").trim();
  return String(text || "").trim();
}

function ClauseRow({ clause, flagged, focused, token, onShowRisks }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const text = withoutHeading(clause.clause_text, clause.heading);
  const long = text.length > CLAMP;
  const shown = long && !open ? text.slice(0, CLAMP).replace(/\s+\S*$/, "") + "…" : text;
  const label = isUnclassified(clause) ? null : clause.predicted_label;
  const title = sentenceCase(clause.heading || clause.section_path || label || `Clause ${clause.clause_index}`);

  useEffect(() => {
    if (focused && ref.current) {
      ref.current.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "center" });
      if (long) setOpen(true);
    }
  }, [focused, token, long]);

  return (
    <article ref={ref} id={"clause-" + clause.clause_index} className={"clause" + (focused ? " clause--focus" : "")}>
      <div className="clause__no" aria-hidden="true">{clause.clause_index}</div>
      <div className="clause__body">
        <header className="clause__head">
          <h4>{title}</h4>
          <div className="clause__tags">
            {label && <span className="tag">{label}</span>}
            {flagged > 0 && (
              <button type="button" className="chip chip--flag" onClick={onShowRisks}>
                {plural(flagged, "flagged term")}
              </button>
            )}
          </div>
        </header>
        <p className="clause__text">{shown}</p>
        {long && <button type="button" className="link" onClick={() => setOpen((value) => !value)}>{open ? "Collapse" : "Read the full clause"}</button>}
      </div>
    </article>
  );
}

export default function ClauseList({ clauses, perClause, focus, onShowRisks }) {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState("labelled");

  // Jumping to a clause must never be hidden by a filter the reader set earlier.
  const token = focus?.token;
  useEffect(() => {
    if (token) { setQuery(""); setMode("all"); }
  }, [token]);

  const counts = useMemo(() => ({
    all: clauses.length,
    labelled: clauses.filter((clause) => !isUnclassified(clause)).length,
    flagged: clauses.filter((clause) => (perClause.get(Number(clause.clause_index)) || 0) > 0).length,
  }), [clauses, perClause]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return clauses.filter((clause) => {
      if (mode === "labelled" && isUnclassified(clause)) return false;
      if (mode === "flagged" && !(perClause.get(Number(clause.clause_index)) > 0)) return false;
      if (!q) return true;
      return [clause.clause_index, clause.predicted_label, clause.heading, clause.section_path, clause.clause_text]
        .some((value) => String(value || "").toLowerCase().includes(q));
    });
  }, [clauses, perClause, query, mode]);

  return (
    <section className="clauses" aria-label="Clauses">
      <div className="clauses__tools">
        <label className="search">
          <span className="sr-only">Search clauses</span>
          <svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="9" cy="9" r="5.5" /><path d="m13.5 13.5 3.5 3.5" /></svg>
          <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search clause text or category" />
        </label>
        <div className="segmented" role="group" aria-label="Show">
          {[["labelled", "Categorised"], ["flagged", "With flags"], ["all", "Everything"]].map(([value, text]) => (
            <button key={value} type="button" className={mode === value ? "on" : ""} onClick={() => setMode(value)}>
              {text} <span>{counts[value]}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="clauses__list">
        {visible.map((clause) => (
          <ClauseRow
            key={clause.clause_index}
            clause={clause}
            flagged={perClause.get(Number(clause.clause_index)) || 0}
            focused={focus != null && String(focus.id) === String(clause.clause_index)}
            token={token}
            onShowRisks={onShowRisks}
          />
        ))}
        {!visible.length && (
          <div className="empty">
            <h3>No clauses match</h3>
            <p>Try another word, or switch to “Everything” to include sections without a category.</p>
          </div>
        )}
      </div>
    </section>
  );
}

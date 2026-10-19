import React, { useEffect, useRef } from "react";

const stripNo = (value) => String(value || "").replace(/^\s*\d+(\.\d+)*[.)]?\s*/, "").trim();

function sentenceCase(value) {
  const text = String(value || "");
  if (text.replace(/[^A-Za-z]/g, "").length < 4 || text !== text.toUpperCase()) return text;
  const lower = text.toLowerCase();
  return lower.charAt(0).toUpperCase() + lower.slice(1);
}

// Many contracts repeat the heading as the first line of the clause body.
function bodyWithoutHeading(text) {
  const lines = String(text || "").split("\n");
  const first = lines[0] || "";
  return lines.length > 1 && first.trim() === first.trim().toUpperCase() && first.trim().length < 90
    ? lines.slice(1).join("\n").trim()
    : String(text || "").trim();
}

// Shows the full text of one clause on demand, so the main view stays about risks.
export default function ClauseDialog({ clause, onClose }) {
  const ref = useRef(null);

  useEffect(() => {
    const node = ref.current;
    if (!node) return undefined;
    if (clause && !node.open) node.showModal();
    if (!clause && node.open) node.close();
    return undefined;
  }, [clause]);

  const heading = clause ? sentenceCase(stripNo(clause.heading || clause.section_path) || `Clause ${clause.clause_index}`) : "";
  return (
    <dialog
      ref={ref}
      className="dialog"
      onClose={onClose}
      onClick={(event) => { if (event.target === ref.current) onClose(); }}
      aria-label={clause ? `Clause ${clause.clause_index}` : "Clause"}
    >
      {clause && (
        <div className="dialog__body">
          <header className="dialog__head">
            <div>
              <p className="dialog__eyebrow">Clause {clause.clause_index}</p>
              <h3>{heading}</h3>
            </div>
            <button type="button" className="button button--quiet button--small" onClick={onClose}>Close</button>
          </header>
          <p className="dialog__text">{bodyWithoutHeading(clause.clause_text)}</p>
        </div>
      )}
    </dialog>
  );
}

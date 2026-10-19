import React, { useState } from "react";

const LIMIT = 300;

export default function Quote({ children, cite, label, onCite }) {
  const text = String(children || "");
  const [open, setOpen] = useState(false);
  const long = text.length > LIMIT;
  const shown = long && !open ? text.slice(0, LIMIT).replace(/\s+\S*$/, "") + "…" : text;
  return (
    <blockquote className="quote">
      <p>“{shown}”</p>
      <footer>
        {cite != null && (
          onCite
            ? <button type="button" className="link" onClick={() => onCite(cite)}>Clause {cite}</button>
            : <span>Clause {cite}</span>
        )}
        {cite == null && label && <span>{label}</span>}
        {long && <button type="button" className="link" onClick={() => setOpen((value) => !value)}>{open ? "Show less" : "Show full wording"}</button>}
      </footer>
    </blockquote>
  );
}

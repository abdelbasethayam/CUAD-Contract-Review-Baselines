import React from "react";
import { humanize } from "../lib/risk.js";

function formatElapsed(seconds) {
  const minutes = Math.floor(seconds / 60);
  const rest = String(seconds % 60).padStart(2, "0");
  return `${minutes}:${rest}`;
}

export default function Progress({ trace, elapsed, onCancel }) {
  const steps = trace.filter((event) => event.type === "progress");
  const current = steps.at(-1);
  const earlier = steps.slice(-5, -1).reverse();

  return (
    <section className="progress" aria-live="polite" aria-label="Analysis progress">
      <div className="progress__head">
        <h2>Reading your contract</h2>
        <span className="progress__clock">{formatElapsed(elapsed)}</span>
      </div>
      <div className="progress__bar" role="progressbar" aria-label="Analysis in progress"><i /></div>
      <p className="progress__now">
        <span className="progress__stage">{humanize(current?.stage) || "Starting"}</span>
        {current?.message || "Preparing the analysis…"}
      </p>
      {earlier.length > 0 && (
        <ul className="progress__done">
          {earlier.map((event, index) => (
            <li key={String(event.stage) + index}><span aria-hidden="true">✓</span>{event.message || humanize(event.stage)}</li>
          ))}
        </ul>
      )}
      <button type="button" className="button button--quiet" onClick={onCancel}>Cancel</button>
    </section>
  );
}

import React from "react";
import Quote from "./Quote.jsx";
import { plural } from "../lib/risk.js";

function Finding({ item, onOpenClause }) {
  return (
    <li className="finding">
      <header className="finding__head">
        <h4>{item.title}</h4>
        <span className="finding__topic">{item.topic}</span>
      </header>
      {item.why && <p className="finding__why">{item.why}</p>}
      {item.evidence.map((entry, index) => (
        <Quote key={index} cite={entry.clause ?? item.clauses[0]} onCite={onOpenClause}>{entry.quote}</Quote>
      ))}
    </li>
  );
}

export default function RiskReview({ review, onOpenClause, partial }) {
  const items = review.topics.flatMap((group) => group.items)
    .sort((a, b) => (a.clauses[0] ?? 1e9) - (b.clauses[0] ?? 1e9));

  if (!items.length && !review.unresolved.length) {
    return (
      <section className="review review--empty">
        <h3>{partial ? "Checks are still running" : "No risks flagged"}</h3>
        <p>{partial
          ? "Flagged terms will appear here as the analysis finishes."
          : "The completed checks found nothing to flag. This is a screening aid, not a guarantee that the contract is free of risk."}</p>
      </section>
    );
  }

  return (
    <section className="review" aria-label="Risks">
      {items.length > 0 && (
        <>
          <div className="review__lead">
            <h3>{plural(items.length, "risk")} to look at</h3>
            <p>Each one shows the exact wording it is based on.</p>
          </div>
          <ol className="findings">
            {items.map((item) => <Finding key={item.key} item={item} onOpenClause={onOpenClause} />)}
          </ol>
        </>
      )}

      {review.unresolved.length > 0 && (
        <details className="unresolved">
          <summary>{plural(review.unresolved.length, "check")} couldn't be completed</summary>
          <p>The contract text didn't give enough to answer these. That doesn't mean they're safe, so give them a manual read.</p>
          <ul>
            {review.unresolved.map((item) => (
              <li key={item.key}>
                <span>{item.title}</span>
                {item.clauses.map((id) => (
                  <button key={id} type="button" className="link" onClick={() => onOpenClause(id)}>Clause {id}</button>
                ))}
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}

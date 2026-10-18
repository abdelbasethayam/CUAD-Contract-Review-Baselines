import React, { useMemo, useState } from "react";
import Quote from "./Quote.jsx";
import { plural } from "../lib/risk.js";

const SCOPE_NOTE = {
  cross_clause: "Across clauses",
  interaction: "Across clauses",
  document: "Whole agreement",
};

function Finding({ item, labels, onOpenClause }) {
  const hasDetail = item.questions.length > 0 || item.sources.length > 0 || item.limitation;
  return (
    <li className="finding">
      <header className="finding__head">
        <h4>{item.title}</h4>
        <div className="finding__refs">
          {SCOPE_NOTE[item.scope] && <span className="tag tag--quiet">{SCOPE_NOTE[item.scope]}</span>}
          {item.clauses.map((id) => (
            <button key={id} type="button" className="chip" onClick={() => onOpenClause(id)} title="Open this clause">
              Clause {id}{labels.get(id) ? ` · ${labels.get(id)}` : ""}
            </button>
          ))}
        </div>
      </header>

      {item.why && <p className="finding__why">{item.why}</p>}

      {item.evidence.map((entry, index) => (
        <Quote key={index} cite={item.clauses.length > 1 || entry.clause !== item.clauses[0] ? entry.clause : null} onCite={onOpenClause}>
          {entry.quote}
        </Quote>
      ))}

      {hasDetail && (
        <div className="finding__next">
          {item.questions.length > 0 && (
            <ul>{item.questions.map((question, index) => <li key={index}>{question}</li>)}</ul>
          )}
          {item.limitation && <p className="muted">{item.limitation}</p>}
          {item.sources.length > 0 && (
            <details className="finding__sources">
              <summary>{plural(item.sources.length, "reference")}</summary>
              <ul>
                {item.sources.map((source, index) => (
                  <li key={index}>{source.url ? <a href={source.url} target="_blank" rel="noreferrer">{source.title}</a> : source.title}</li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
    </li>
  );
}

export default function RiskReview({ review, clauses, onOpenClause, partial }) {
  const [topic, setTopic] = useState("all");
  const labels = useMemo(() => new Map(clauses.map((clause) => [Number(clause.clause_index), clause.predicted_label && !/unclassified|no applicable/i.test(clause.predicted_label) ? clause.predicted_label : null])), [clauses]);
  const visible = topic === "all" ? review.topics : review.topics.filter((group) => group.label === topic);

  if (!review.total && !review.unresolved.length) {
    return (
      <section className="review review--empty">
        <h3>{partial ? "Checks are still running" : "Nothing flagged"}</h3>
        <p>{partial
          ? "Flagged terms will appear here as the analysis completes."
          : "The completed checks did not flag any terms. This is a screening aid, so it isn't a guarantee that the contract is free of risk."}</p>
      </section>
    );
  }

  return (
    <section className="review" aria-label="Terms to review">
      <div className="review__lead">
        <h3>
          {review.total
            ? <>{plural(review.total, "term")} worth a closer look</>
            : "No terms flagged"}
        </h3>
        <p>
          {review.total
            ? `Spread across ${plural(review.topics.length, "area")} of the agreement. Each one links to the exact wording.`
            : "Some checks could not be resolved. See the list below."}
        </p>
      </div>

      {review.topics.length > 1 && (
        <div className="topic-filter" role="group" aria-label="Filter by area">
          <button type="button" className={"pill" + (topic === "all" ? " pill--on" : "")} onClick={() => setTopic("all")}>
            All <span>{review.total}</span>
          </button>
          {review.topics.map((group) => (
            <button key={group.label} type="button" className={"pill" + (topic === group.label ? " pill--on" : "")} onClick={() => setTopic(group.label)}>
              {group.label} <span>{group.items.length}</span>
            </button>
          ))}
        </div>
      )}

      {visible.map((group) => (
        <section key={group.label} className="topic">
          <h3 className="topic__title">{group.label}<span>{group.items.length}</span></h3>
          {group.items[0]?.focus && <p className="topic__focus"><strong>What to check</strong> {group.items[0].focus}</p>}
          <ol className="findings">
            {group.items.map((item) => <Finding key={item.key} item={item} labels={labels} onOpenClause={onOpenClause} />)}
          </ol>
        </section>
      ))}

      {review.unresolved.length > 0 && (
        <details className="unresolved">
          <summary>{plural(review.unresolved.length, "check")} could not be completed</summary>
          <p>
            The contract text did not give enough to answer these. That does not mean the clauses are safe, so they are worth
            a manual read.
          </p>
          <ul>
            {review.unresolved.map((item) => (
              <li key={item.key}>
                <span>{item.title}</span>
                {item.clauses.map((id) => (
                  <button key={id} type="button" className="chip" onClick={() => onOpenClause(id)}>Clause {id}</button>
                ))}
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}

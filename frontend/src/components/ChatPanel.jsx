import React, { useEffect, useRef, useState } from "react";
import RichText from "./RichText.jsx";
import Quote from "./Quote.jsx";
import { plural } from "../lib/risk.js";

const STARTERS = [
  "Who can terminate this agreement, and on what notice?",
  "How do the two parties' liability caps compare?",
  "Which law governs, and where would disputes be heard?",
  "What happens to our data when the contract ends?",
];

function Sources({ citations, onOpenClause }) {
  return (
    <details className="sources" open={citations.length <= 2}>
      <summary>{plural(citations.length, "passage")} from the contract</summary>
      {citations.map((citation, index) => (
        <Quote
          key={String(citation.source_type || "clause") + String(citation.field || citation.clause_index) + index}
          cite={citation.clause_index}
          label={citation.source_label}
          onCite={citation.clause_index != null ? onOpenClause : undefined}
        >
          {citation.quote}
        </Quote>
      ))}
    </details>
  );
}

export default function ChatPanel({ name, messages, loading, error, onAsk, onClear, onOpenClause, disabled }) {
  const [draft, setDraft] = useState("");
  const scroller = useRef(null);
  const field = useRef(null);

  useEffect(() => {
    const node = scroller.current;
    if (node) node.scrollTo({ top: node.scrollHeight, behavior: "smooth" });
  }, [messages.length, loading]);

  useEffect(() => {
    const node = field.current;
    if (!node) return;
    node.style.height = "auto";
    node.style.height = Math.min(node.scrollHeight, 150) + "px";
  }, [draft]);

  function send() {
    const question = draft.trim();
    if (!question || loading || disabled) return;
    setDraft("");
    onAsk(question);
  }

  const last = messages.at(-1);
  const followUps = last?.role === "assistant" && !loading ? (last.follow_up_questions || []).slice(0, 3) : [];

  return (
    <section className="chat" aria-label="Ask this contract">
      <header className="chat__head">
        <div>
          <h2>Ask this contract</h2>
          <p>Answers come from the wording of {name || "your document"}.</p>
        </div>
        {messages.length > 0 && <button type="button" className="link" onClick={onClear} disabled={loading}>New chat</button>}
      </header>

      <div className="chat__scroll" ref={scroller} aria-live="polite">
        {!messages.length && (
          <div className="chat__empty">
            <p>Ask in plain language. Every answer points back to the clause it relied on, and says so when the contract doesn't cover the question.</p>
            <div className="starters">
              {STARTERS.map((question) => (
                <button key={question} type="button" onClick={() => onAsk(question)} disabled={loading || disabled}>{question}</button>
              ))}
            </div>
          </div>
        )}

        {messages.map((message, index) => (
          message.role === "user" ? (
            <div key={index} className="msg msg--user"><p>{message.text}</p></div>
          ) : (
            <div key={index} className="msg msg--assistant">
              <RichText text={message.answer} />
              {message.insufficient_evidence && message.model !== "SOURCE_EXCERPTS" && message.model !== "EXTRACTIVE_FALLBACK" && <p className="msg__note">The contract text gives limited support for this answer.</p>}
              {message.model === "EXTRACTIVE_FALLBACK" && <p className="msg__note">The language model was unavailable, so this answer only quotes the contract.</p>}
              {message.citations?.length > 0 && <Sources citations={message.citations} onOpenClause={onOpenClause} />}
            </div>
          )
        ))}

        {loading && <div className="msg msg--assistant msg--typing" aria-label="Reading the contract"><i /><i /><i /></div>}
        {followUps.length > 0 && (
          <div className="followups">
            {followUps.map((question) => <button key={question} type="button" onClick={() => onAsk(question)}>{question}</button>)}
          </div>
        )}
      </div>

      {error && <div className="notice notice--error" role="alert">{error}</div>}

      <form className="composer" onSubmit={(event) => { event.preventDefault(); send(); }}>
        <textarea
          ref={field}
          rows={1}
          value={draft}
          maxLength={1200}
          disabled={disabled}
          placeholder={disabled ? "Available when the analysis finishes" : "Ask about a clause, a right, or a risk"}
          aria-label="Your question"
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault();
              send();
            }
          }}
        />
        <button type="submit" className="composer__send" disabled={!draft.trim() || loading || disabled} aria-label="Send question">
          <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M10 16V5m0 0-4.5 4.5M10 5l4.5 4.5" /></svg>
        </button>
      </form>
      <p className="chat__foot">AI-assisted and not legal advice. Check the quoted wording before relying on an answer.</p>
    </section>
  );
}

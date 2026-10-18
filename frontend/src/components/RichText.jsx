import React from "react";

function inline(text) {
  return String(text).split(/(\*\*[^*]+\*\*)/g).map((part, index) =>
    part.startsWith("**") && part.endsWith("**") && part.length > 4
      ? <strong key={index}>{part.slice(2, -2)}</strong>
      : part
  );
}

const BULLET = /^\s*(?:[-*•]|\d+[.)])\s+/;

// Small, safe renderer for assistant answers: paragraphs, bullet lists and **bold**.
export default function RichText({ text }) {
  const blocks = String(text || "").trim().split(/\n{2,}/).filter(Boolean);
  return (
    <div className="rich">
      {blocks.map((block, index) => {
        const lines = block.split("\n").filter((line) => line.trim());
        if (lines.length && lines.every((line) => BULLET.test(line))) {
          return <ul key={index}>{lines.map((line, i) => <li key={i}>{inline(line.replace(BULLET, ""))}</li>)}</ul>;
        }
        return (
          <p key={index}>
            {lines.map((line, i) => <React.Fragment key={i}>{i > 0 && <br />}{inline(line)}</React.Fragment>)}
          </p>
        );
      })}
    </div>
  );
}

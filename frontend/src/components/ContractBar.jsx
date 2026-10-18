import React from "react";
import { appPath } from "../lib/api.js";
import { plural } from "../lib/risk.js";

function Fact({ label, value }) {
  if (!value) return null;
  return <div className="fact"><dt>{label}</dt><dd>{value}</dd></div>;
}

export default function ContractBar({ result, review, clauseCount }) {
  const meta = result.contract_metadata || {};
  const parties = Array.isArray(meta.parties) && meta.parties.length ? meta.parties.join("  ·  ") : null;
  const term = meta.expiration_date || meta.expiration_terms || null;
  const effective = meta.effective_date || meta.effective_date_condition || null;
  const bundle = result.downloads?.contract_bundle_zip;

  return (
    <section className="contract-bar" aria-label="Contract summary">
      <div className="contract-bar__top">
        <div className="contract-bar__title">
          {result.demo_mode && <span className="tag">Sample analysis</span>}
          <h2>{meta.name || result.filename}</h2>
          <p>{plural(clauseCount, "clause")} read · {plural(review.total, "term")} to review</p>
        </div>
        {bundle && (
          <a className="button button--secondary contract-bar__download" href={appPath(bundle)} download>
            Download package
          </a>
        )}
      </div>
      <dl className="contract-bar__facts">
        <Fact label="Parties" value={parties} />
        <Fact label="Governing law" value={meta.governing_law} />
        <Fact label="Effective" value={effective} />
        <Fact label="Term" value={term} />
        <Fact label="Agreement date" value={meta.agreement_date} />
      </dl>
    </section>
  );
}

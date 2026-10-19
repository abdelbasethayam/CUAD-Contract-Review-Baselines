import React from "react";
import { appPath } from "../lib/api.js";

export default function ContractBar({ result }) {
  const meta = result.contract_metadata || {};
  const parties = Array.isArray(meta.parties) && meta.parties.length ? meta.parties.join(" and ") : null;
  const bundle = result.downloads?.contract_bundle_zip;
  const details = [parties, meta.governing_law && `Governing law: ${meta.governing_law}`].filter(Boolean);

  return (
    <section className="contract-bar" aria-label="Contract">
      <div>
        {result.demo_mode && <span className="tag">Sample</span>}
        <h2>{meta.name || result.filename}</h2>
        {details.length > 0 && <p>{details.join(" · ")}</p>}
      </div>
      {bundle && <a className="button button--secondary" href={appPath(bundle)} download>Download</a>}
    </section>
  );
}

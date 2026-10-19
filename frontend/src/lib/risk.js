// Turns the raw analysis payload into something a reviewer can act on:
// findings grouped by area of the agreement, de-duplicated, with the exact
// quoted wording attached. No severity or probability is invented here — the
// backend deliberately does not produce one (see data/risk/RISK_SCORE_POLICY.md).

const DOMAIN_LABELS = {
  "Liability Risk": "Liability and indemnity",
  "Financial Risk": "Payment and fees",
  "Termination Risk": "Termination and exit",
  "Operational Risk": "Service and operations",
  "Compliance Risk": "Compliance",
  "Insurance Risk": "Insurance",
  "Intellectual Property Risk": "IP and data",
  "Assignment / Control Risk": "Assignment and control",
  "Dispute Resolution Risk": "Disputes and governing law",
  "Commercial Risk": "Commercial terms",
};

// Mirrors backend/data/legal_knowledge/risk_taxonomy.json (mitigation_guidance).
const DOMAIN_FOCUS = {
  "Liability Risk": "Review cap structure, carve-outs, claim scope, defense control, and exclusions.",
  "Financial Risk": "Review caps, calculation mechanics, exclusions, notice, cure, and payment controls.",
  "Termination Risk": "Review notice, cause, cure, transition, survival, and post-termination obligations.",
  "Operational Risk": "Review measurable obligations, remedies, transition support, and continuity controls.",
  "Compliance Risk": "Review applicable laws, audit scope, records, notice, remediation, and allocation of responsibility.",
  "Insurance Risk": "Review policy types, limits, duration, certificates, additional insured status, and notice of cancellation.",
  "Intellectual Property Risk": "Review subject matter, scope, territory, duration, exclusivity, ownership, and sublicensing.",
  "Assignment / Control Risk": "Review permitted transfers, affiliates, control changes, consent standards, and termination consequences.",
  "Dispute Resolution Risk": "Review forum, seat, rules, governing law, escalation, confidentiality, and cost allocation.",
  "Commercial Risk": "Review scope, duration, minimums, adjustment rights, renewal notice, and exit mechanics.",
};

const INFERENCE = [
  [/liabilit|indemn|damages|cap on/i, "Liability Risk"],
  [/insurance/i, "Insurance Risk"],
  [/terminat|transition|exit|renewal/i, "Termination Risk"],
  [/assign|change of control|control/i, "Assignment / Control Risk"],
  [/intellectual|\bip\b|licen[sc]e|ownership|confidential|data/i, "Intellectual Property Risk"],
  [/governing|law|forum|dispute|arbitrat|jurisdiction|venue/i, "Dispute Resolution Risk"],
  [/fee|payment|refund|price|pricing|invoice|penalt|liquidated/i, "Financial Risk"],
  [/precedence|online terms|minimum|commitment|exclusiv/i, "Commercial Risk"],
  [/complian|audit|regulat/i, "Compliance Risk"],
];

export function inferDomain(...parts) {
  const text = parts.filter(Boolean).join(" ");
  for (const [pattern, domain] of INFERENCE) if (pattern.test(text)) return domain;
  return null;
}

export const topicLabel = (domain) => DOMAIN_LABELS[domain] || "Other terms";
export const topicFocus = (domain) => DOMAIN_FOCUS[domain] || null;

export function humanize(value) {
  const text = String(value || "").replaceAll("_", " ").trim();
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : "";
}

export function isUnclassified(clause) {
  return clause.classification_status === "NO_APPLICABLE_LABEL"
    || clause.predicted_label === "NO_APPLICABLE_LABEL"
    || clause.predicted_label === "No applicable label"
    || clause.predicted_label === "UNCLASSIFIED"
    || !clause.predicted_label;
}

function evidenceOf(raw, fallbackClause) {
  const evidence = raw.evidence;
  if (Array.isArray(evidence)) {
    return evidence
      .map((item) => ({ clause: item?.clause_id ?? item?.clause_index ?? fallbackClause, quote: String(item?.quote ?? item?.text ?? "").trim() }))
      .filter((item) => item.quote);
  }
  const quote = String(evidence || "").trim();
  return quote ? [{ clause: raw.evidence_clause_index ?? fallbackClause, quote }] : [];
}

function clausesOf(raw, owner) {
  const ids = [];
  if (Array.isArray(raw.clause_ids) && raw.clause_ids.length) ids.push(...raw.clause_ids);
  else if (owner != null) ids.push(owner);
  else if (raw.clause_index != null) ids.push(raw.clause_index);
  return [...new Set(ids.map((id) => Number(id)).filter((id) => Number.isFinite(id)))].sort((a, b) => a - b);
}

function sourcesOf(raw) {
  return (raw.supporting_sources || [])
    .map((source) => ({
      title: source.source_title || source.source_name || source.citation || source.title || source.name || source.id || "",
      url: source.source_url || source.url || null,
    }))
    .filter((source) => source.title);
}

function normalise(raw, { owner, scope, label }) {
  const clauses = clausesOf(raw, owner);
  const domain = raw.risk_domain
    || raw.risk_domains?.[0]
    || inferDomain(raw.risk_type, raw.question, raw.name, label);
  return {
    key: `${raw.check_id || raw.id || raw.risk_type}|${clauses.join(",")}`,
    id: raw.check_id || raw.id || null,
    title: raw.risk_type || raw.question || humanize(raw.name) || "Point to review",
    why: raw.why_flagged || raw.reason || "",
    evidence: evidenceOf(raw, clauses[0]),
    clauses,
    domain,
    topic: topicLabel(domain),
    focus: raw.review_focus || topicFocus(domain),
    questions: Array.isArray(raw.review_questions) ? raw.review_questions : [],
    limitation: raw.limitation || null,
    scope,
    status: raw.risk_status || "POTENTIAL_RISK",
    sources: sourcesOf(raw),
  };
}

export function buildReview(result) {
  const clauses = result?.clauses || [];
  const assessment = result?.contract_risk_assessment || {};
  const seen = new Set();
  const flagged = [];
  const unresolved = [];

  const add = (item) => {
    if (seen.has(item.key)) return;
    seen.add(item.key);
    (item.status === "INSUFFICIENT_EVIDENCE" ? unresolved : flagged).push(item);
  };

  for (const clause of clauses) {
    for (const finding of clause.risk_findings || []) {
      if (finding.risk_status === "NO_RISK" || finding.risk_status === "ERROR") continue;
      add(normalise(finding, { owner: clause.clause_index, scope: "clause", label: clause.predicted_label }));
    }
  }
  for (const finding of assessment.cross_clause_findings || []) {
    if (finding.risk_status === "NO_RISK" || finding.risk_status === "ERROR") continue;
    add(normalise(finding, { owner: null, scope: "cross_clause" }));
  }
  for (const finding of assessment.document_findings || []) {
    if (finding.risk_status === "NO_RISK" || finding.risk_status === "ERROR") continue;
    add(normalise(finding, { owner: null, scope: "document" }));
  }

  // Rule-based interaction signals often restate a model finding. Only keep the ones that add something.
  const knownIds = new Set(flagged.concat(unresolved).map((item) => item.id).filter(Boolean));
  for (const signal of assessment.deterministic_cross_checks || []) {
    if (signal.id && knownIds.has(signal.id)) continue;
    const evidenceClauses = (signal.evidence || []).map((item) => item.clause_id).filter((id) => id != null);
    add(normalise({ ...signal, clause_ids: evidenceClauses, risk_status: "POTENTIAL_RISK" }, { owner: null, scope: "interaction" }));
  }

  const byTopic = new Map();
  for (const item of flagged) {
    if (!byTopic.has(item.topic)) byTopic.set(item.topic, []);
    byTopic.get(item.topic).push(item);
  }
  const topics = [...byTopic.entries()]
    .map(([label, items]) => ({
      label,
      items: items.sort((a, b) => (a.clauses[0] ?? 1e9) - (b.clauses[0] ?? 1e9)),
    }))
    .sort((a, b) => b.items.length - a.items.length || a.label.localeCompare(b.label));

  const perClause = new Map();
  for (const item of flagged) for (const id of item.clauses) perClause.set(id, (perClause.get(id) || 0) + 1);

  return {
    topics,
    unresolved: unresolved.sort((a, b) => (a.clauses[0] ?? 1e9) - (b.clauses[0] ?? 1e9)),
    total: flagged.length,
    perClause,
  };
}

export function plural(count, singular, pluralForm) {
  return `${count} ${count === 1 ? singular : (pluralForm || singular + "s")}`;
}

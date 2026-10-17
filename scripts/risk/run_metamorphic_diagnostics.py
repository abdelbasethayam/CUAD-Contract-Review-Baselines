#!/usr/bin/env python3
"""Run controlled, authored metamorphic checks; not a gold-label accuracy benchmark."""
from __future__ import annotations
import hashlib, json, os, re, sys, time
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'backend'))
from scripts.risk.run_cross_document_model_scenarios import split_clauses, sha
from backend.app.core.risk import contract_checks as contract_checks
analyze_contract_checks = contract_checks.analyze_contract_checks
# A single-check diagnostic needs a compact structured response; cap generation so a malformed verbose answer cannot stall the suite.
contract_checks.RISK_MAX_TOKENS = 768
from backend.app.core.risk.deterministic_cross_checks import run_deterministic_cross_checks
from backend.app.core.risk.risk_playbook import load_playbook
from backend.app.core.config import RISK_MODEL as CONFIGURED_RISK_MODEL
FIXTURE=ROOT/'data/risk/evaluation/cross_document_v1/positive_risk_stress_contract.txt'
OUT=ROOT/'data/risk/results/metamorphic_diagnostics.json'
MD=ROOT/'data/risk/results/metamorphic_diagnostics.md'

def reindex(clauses):
    return [{**c,'clause_index':i} for i,c in enumerate(clauses)]
def make_case(case_id, description, target, transform, relation):
    return {'case_id':case_id,'description':description,'target_check':target,'transform':transform,'expected_relation':relation}
def main():
    playbook=load_playbook(); checks={x['id']:x for x in playbook.get('cross_clause_checks',[])}
    original=split_clauses(FIXTURE)
    base_text=FIXTURE.read_text(encoding='utf-8')
    def all_liability_removed(cs):
        # Exclude all sections that can support liability-cap/uncapped-overlap reasoning.
        return [c for c in cs if not any(k in c['clause_text'].upper() for k in ('LIABILITY CAP','LIQUIDATED DAMAGES','INDEMNIFICATION','INSURANCE'))]
    def negated(cs):
        out=[]
        for c in cs:
            t=c['clause_text']; heading=t.splitlines()[0].upper()
            if t.upper().startswith('1. LIABILITY CAP.'):
                t='1. LIABILITY CAP. Supplier liability is capped at $100,000, including indemnification obligations and liquidated damages. No liability head is outside or uncapped under this Agreement.'
            elif t.upper().startswith('2. LIQUIDATED DAMAGES.'):
                t='2. LIQUIDATED DAMAGES. Liquidated damages for delay are expressly subject to and included within the liability cap.'
            elif t.upper().startswith('10. INDEMNIFICATION.'):
                t='10. INDEMNIFICATION. Indemnification obligations are expressly subject to and included within the liability cap.'
            elif t.upper().startswith('9. INSURANCE.'):
                t='9. INSURANCE. Required insurance limits are $150,000 and the contractual liability cap is $100,000.'
            out.append({**c,'clause_text':t})
        return out
    def scoped(cs):
        out=[]
        for c in cs:
            t=c['clause_text']; heading=t.splitlines()[0].upper()
            if t.upper().startswith('1. LIABILITY CAP.'):
                t='1. LIABILITY CAP. Supplier liability is capped at $100,000, except that third-party indemnification obligations only are outside the cap; all other liability heads are capped.'
            elif t.upper().startswith('10. INDEMNIFICATION.'):
                t='10. INDEMNIFICATION. Only third-party indemnification obligations are expressly outside the liability cap.'
            out.append({**c,'clause_text':t})
        return out
    def repair_x4(cs):
        out=[]
        for c in cs:
            t=c['clause_text']; heading=t.splitlines()[0].upper()
            if t.upper().startswith('4. CONVENIENCE TERMINATION AND MINIMUMS.'):
                t='4. CONVENIENCE TERMINATION AND MINIMUMS. Customer may terminate for convenience on 30 days notice and owes no future minimum commitments or fees for periods after the effective termination date.'
            out.append({**c,'clause_text':t})
        return out
    cases=[
      make_case('X1-BASELINE','Original risk-stress fixture','X-1',lambda c:c,'POTENTIAL_RISK expected for constructed stress case; exact evidence required.'),
      make_case('X1-EVIDENCE-DELETION','Remove every liability/insurance/indemnification/liquidated-damages section','X-1',all_liability_removed,'Must not assert POTENTIAL_RISK for X-1 without new evidence from remaining clauses.'),
      make_case('X1-NEGATION-CONTROL','Make all liability heads including indemnification and liquidated damages subject to cap','X-1',negated,'Should move away from POTENTIAL_RISK; NO_RISK or abstention is acceptable.'),
      make_case('X1-SCOPE-CHANGE','Narrow the exception to third-party indemnification only','X-1',scoped,'If positive, rationale must preserve the narrowed scope; otherwise abstain.'),
      make_case('X1-REPAIR','Same liability-cap repair as negation/control insertion','X-1',negated,'Should move away from POTENTIAL_RISK; NO_RISK or abstention is acceptable.'),
      make_case('X1-MISSING-CONTEXT','Remove all sections needed to compare cap and exceptions','X-1',all_liability_removed,'Should abstain or report NO_RISK, not claim a supported positive interaction.'),
      make_case('X1-ORDER-INVARIANCE','Reverse the independent clause order','X-1',lambda c:list(reversed(c)),'Status should match baseline; evidence locators may change.'),
      make_case('X1-DUPLICATE-UNRELATED','Duplicate the unrelated critical-software clause','X-1',lambda c:c+[next(x for x in c if 'CRITICAL SOFTWARE' in x['clause_text'].upper())],'Status should match baseline; unrelated duplication should not create a new X-1 risk.'),
      make_case('X4-BASELINE','Original early-termination/minimum-commitment interaction','X-4',lambda c:c,'Constructed stress case expected POTENTIAL_RISK; exact evidence required.'),
      make_case('X4-EXIT-REPAIR','Remove post-termination future minimums/fees','X-4',repair_x4,'Should move away from POTENTIAL_RISK; NO_RISK or abstention is acceptable.'),
    ]
    results=[]; baseline={}
    model=os.environ.get('RISK_MODEL',CONFIGURED_RISK_MODEL)
    for case in cases:
        target=checks[case['target_check']]
        clauses=reindex(case['transform']([dict(x) for x in original]))
        if len(clauses)<3: raise RuntimeError(f"Fixture became too small: {case['case_id']}")
        t0=time.monotonic()
        cross,doc=analyze_contract_checks(clauses,playbook={'cross_clause_checks':[target],'document_level_checks':[]},passes=1,deterministic_signals=run_deterministic_cross_checks(clauses))
        elapsed=round(time.monotonic()-t0,3)
        item=next((x for x in cross+doc if x.get('check_id')==case['target_check']),None)
        if item is None: item={'check_id':case['target_check'],'risk_status':'INSUFFICIENT_EVIDENCE','answer':"DON'T KNOW",'evidence':[],'clause_ids':[],'why_flagged':'No target output returned.'}
        by_id={int(c['clause_index']):c['clause_text'] for c in clauses}
        evidence=item.get('evidence') or []
        exact=[]
        for ev in evidence:
            try: idx=int(ev.get('clause_id')); quote=str(ev.get('quote') or ''); exact.append(bool(quote and idx in by_id and quote in by_id[idx]))
            except Exception: exact.append(False)
        status=item.get('risk_status','MISSING')
        if case['case_id'] in ('X1-BASELINE','X4-BASELINE'): baseline[case['target_check']]={'status':status,'why':item.get('why_flagged','')}
        base=baseline.get(case['target_check'])
        if case['case_id'] in ('X1-BASELINE','X4-BASELINE'):
            relation_pass=(status=='POTENTIAL_RISK' and bool(evidence) and bool(exact) and all(exact))
        elif case['case_id']=='X1-SCOPE-CHANGE':
            rationale=(str(item.get('why_flagged',''))+' '+json.dumps(evidence)).lower()
            relation_pass=(status!='POTENTIAL_RISK' or ('third-party' in rationale or 'third party' in rationale))
        elif case['case_id'] in ('X1-ORDER-INVARIANCE','X1-DUPLICATE-UNRELATED'):
            relation_pass=bool(base and status==base['status'])
        elif case['case_id']=='X4-EXIT-REPAIR':
            # A repair only demonstrates the expected transition if the unmodified stress case first flags.
            relation_pass=bool(base and base['status']=='POTENTIAL_RISK' and status!='POTENTIAL_RISK')
        else:
            relation_pass=status!='POTENTIAL_RISK'
        results.append({'case_id':case['case_id'],'description':case['description'],'target_check':case['target_check'],'expected_relation':case['expected_relation'],'observed_status':status,'observed_answer':item.get('answer'),'why_flagged':item.get('why_flagged',''),'evidence':evidence,'evidence_quotes_exact':exact,'evidence_all_exact':bool(evidence) and all(exact),'relation_pass':bool(relation_pass),'elapsed_seconds':elapsed,'clause_count':len(clauses),'fixture_sha256':sha(FIXTURE),'playbook_sha256':sha(ROOT/'data/risk/commercial_clause_risk_playbook.json'),'analyzer_sha256':sha(ROOT/'backend/app/core/risk/contract_checks.py'),'runner_sha256':sha(Path(__file__)),'model_config':model,'label_provenance':'AUTHORED_METAMORPHIC_SPECIFICATION_NOT_HUMAN_GOLD'})
        checkpoint={'schema_version':1,'status':'RUNNING','created_at_utc':datetime.now(timezone.utc).isoformat(),'case_count':len(results),'relation_pass_count':sum(bool(x['relation_pass']) for x in results),'relation_pass_rate':sum(bool(x['relation_pass']) for x in results)/len(results),'case_results':results,'evaluation_type':'METAMORPHIC_CONSISTENCY_NOT_ACCURACY','checkpoint':True}
        OUT.write_text(json.dumps(checkpoint,indent=2,ensure_ascii=False),encoding='utf-8')
        print(f"[DONE] {case['case_id']}: {status}, relation_pass={relation_pass}, {elapsed}s",flush=True)
    report={'schema_version':1,'status':'COMPLETED','created_at_utc':datetime.now(timezone.utc).isoformat(),'evaluation_type':'METAMORPHIC_CONSISTENCY_NOT_ACCURACY','case_count':len(results),'relation_pass_count':sum(x['relation_pass'] for x in results),'relation_pass_rate':sum(x['relation_pass'] for x in results)/len(results),'case_results':results,'model_config':model,'source_fixture_sha256':sha(FIXTURE),'playbook_sha256':sha(ROOT/'data/risk/commercial_clause_risk_playbook.json'),'analyzer_sha256':sha(ROOT/'backend/app/core/risk/contract_checks.py'),'runner_sha256':sha(Path(__file__)),'limitations':['Authored transformations test specified relationships, not legal correctness.','The LLM is nondeterministic; a failed relation is a counterexample to investigate, not a gold-label error.','No human-gold labels were used.']}
    OUT.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    lines=['# Metamorphic diagnostics — Phase 2','',f"- Status: {report['status']}",f"- Cases: {report['case_count']}",f"- Relation checks passed: {report['relation_pass_count']}/{report['case_count']} ({report['relation_pass_rate']:.1%})",'- Interpretation: controlled consistency diagnostics, **not** real-contract accuracy or legal correctness.','', '| Case | Target | Observed | Relation | Time |','|---|---|---|---|---:|']
    for x in results: lines.append(f"| {x['case_id']} | {x['target_check']} | {x['observed_status']} | {'PASS' if x['relation_pass'] else 'FAIL'} | {x['elapsed_seconds']:.1f}s |")
    lines += ['', '## Counterexamples', '']
    for x in results:
        if not x['relation_pass']: lines += [f"### {x['case_id']}",f"- Expected relation: {x['expected_relation']}",f"- Observed: {x['observed_status']} / {x.get('observed_answer')}",f"- Rationale: {x.get('why_flagged') or '(none)' }",f"- Evidence: `{json.dumps(x.get('evidence') or [],ensure_ascii=False)}`",'']
    lines += ['## Provenance','',f"- Model config: `{model}`",f"- Fixture SHA-256: `{report['source_fixture_sha256']}`",f"- Playbook SHA-256: `{report['playbook_sha256']}`",f"- Analyzer SHA-256: `{report['analyzer_sha256']}`",f"- Runner SHA-256: `{report['runner_sha256']}`",'- Labels: `AUTHORED_METAMORPHIC_SPECIFICATION_NOT_HUMAN_GOLD`.','']
    MD.write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({'status':report['status'],'cases':report['case_count'],'passed':report['relation_pass_count'],'rate':report['relation_pass_rate'],'json':str(OUT.relative_to(ROOT)),'markdown':str(MD.relative_to(ROOT))},indent=2))
if __name__=='__main__': raise SystemExit(main())

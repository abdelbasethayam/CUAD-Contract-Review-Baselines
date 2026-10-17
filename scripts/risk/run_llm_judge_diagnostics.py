#!/usr/bin/env python3
"""Two-model rubric diagnostics for existing synthetic scenarios; never gold labels."""
from __future__ import annotations
import argparse,hashlib,json,sys,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'backend'))
from backend.app.core.rag.generator import call_ollama
from scripts.risk.run_cross_document_model_scenarios import sha
IN=ROOT/'data/risk/results/cross_document_model_scenarios.jsonl'
OUT=ROOT/'data/risk/results/llm_judge_diagnostics.json'
MD=ROOT/'data/risk/results/llm_judge_diagnostics.md'
MODELS=['qwen3:8b','llama3.1:8b']

def parse_json(raw):
    s=str(raw or '').strip()
    try:return json.loads(s)
    except Exception:
        import re
        m=re.search(r'\{.*\}',s,re.S)
        if m:
            try:return json.loads(m.group())
            except Exception:pass
    return None

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args()
    rows=[json.loads(x) for x in IN.read_text(encoding='utf-8').splitlines() if x.strip()]
    # Avoid judging stale or duplicate rows: one record per scenario id, prefer latest row.
    by_id={r['scenario_id']:r for r in rows}
    rows=list(by_id.values())
    fixtures={}
    for r in rows: fixtures.setdefault(r['scenario_type'],r['fixture_file'])
    results=[]; prompt_hashes={}; input_refresh_note=None
    if args.resume and OUT.exists():
        previous=json.loads(OUT.read_text(encoding='utf-8'))
        if previous.get('input_sha256') == sha(IN):
            results=list(previous.get('results') or [])
            prompt_hashes=dict(previous.get('prompt_sha256') or {})
            input_refresh_note=previous.get('input_refresh_note')
    for fixture_type,fixture_rel in sorted(fixtures.items()):
        fixture_text=(ROOT/fixture_rel).read_text(encoding='utf-8')
        group=sorted([r for r in rows if r['scenario_type']==fixture_type],key=lambda x:x['scenario_id'])
        source=[]
        for r in group:
            source.append({'scenario_id':r['scenario_id'],'check_id':r['check_id'],'scope':r.get('scope'),'observed_status':r.get('observed_status'),'observed_answer':r.get('observed_answer'),'why_flagged':r.get('observed_why_flagged'),'evidence':r.get('observed_evidence') or [],'clause_ids':r.get('observed_clause_ids') or []})
        for model in MODELS:
            already={x.get('scenario_id') for x in results if x.get('scenario_type')==fixture_type and x.get('model')==model}
            if len(already)==len(group):
                print(f'[SKIP] {fixture_type}/{model}: checkpoint already complete',flush=True)
                continue
            prompt=f'''You are an independent diagnostic reviewer of machine-generated contract-risk findings on a SYNTHETIC contract fixture. This is NOT a legal opinion and you do not have a gold label. Do not guess what an evaluator expects. Assess only the supplied text and claims.

Rubric for each finding:
- claim_supported: true only if the stated status/rationale is reasonably supported by supplied contract text; false if contradicted or unsupported; null if genuinely indeterminate.
- interaction_supported: for cross-clause/document findings, true only if the cited text supports the claimed relationship across provisions; false if the relationship is not shown; null if unclear.
- uncertainty_appropriate: true if abstention/INSUFFICIENT_EVIDENCE is used when necessary, false if a confident conclusion is made despite missing context, null if not assessable.
- external_law_claim: true only if the finding makes an assertion about external law/enforceability/regulatory status rather than describing contract text.
- concerns: concise list of specific unsupported/contradicted aspects, empty if none.
- confidence: integer 1-5 about your rubric assessment, not probability that legal risk exists.
Do not use outside law. Do not infer the intended scenario outcome. For a NO_RISK finding with no evidence quotes, judge whether its explanation is supported by the provided text and context, not whether all conceivable risks are absent.
Return JSON only: {{"judgments":[{{"scenario_id":"...","claim_supported":true,"interaction_supported":true,"uncertainty_appropriate":true,"external_law_claim":false,"concerns":[],"confidence":3,"rationale":"brief"}}]}}. Include every scenario_id exactly once.

SOURCE CONTRACT (fixture type {fixture_type})
{fixture_text}

OBSERVED FINDINGS (no expected statuses or authored rationales supplied)
{json.dumps(source,ensure_ascii=False)}
'''
            ph=hashlib.sha256(prompt.encode()).hexdigest();prompt_hashes[f'{fixture_type}/{model}']=ph
            started=time.monotonic(); raw=''; parsed=None; error=None
            try:
                raw=call_ollama(prompt,model=model,temperature=0.0,num_ctx=8192,max_tokens=1800,think=False)
                parsed=parse_json(raw)
                if not isinstance(parsed,dict) or not isinstance(parsed.get('judgments'),list):
                    # One bounded repair attempt, retaining the same evidence and rubric.
                    raw=call_ollama('Return only valid JSON matching the schema. Do not add commentary. Repair this attempted JSON response without changing the intended judgments:\n'+str(raw),model=model,temperature=0.0,num_ctx=8192,max_tokens=1800,think=False)
                    parsed=parse_json(raw)
                if not isinstance(parsed,dict) or not isinstance(parsed.get('judgments'),list): error='invalid_json_or_missing_judgments'
            except Exception as exc: error=type(exc).__name__+': '+str(exc)[:300]
            elapsed=round(time.monotonic()-started,2)
            judged={str(x.get('scenario_id')):x for x in (parsed or {}).get('judgments',[]) if isinstance(x,dict)}
            for r in group:
                j=judged.get(r['scenario_id'])
                contract=(ROOT/r['fixture_file']).read_text(encoding='utf-8')
                # Exact quote existence is deterministic and independent of the LLM judge.
                evs=r.get('observed_evidence') or []
                exact=[]
                for ev in evs:
                    quote=str(ev.get('quote') or '')
                    exact.append(bool(quote and quote in contract))
                results.append({'scenario_id':r['scenario_id'],'scenario_type':fixture_type,'check_id':r['check_id'],'model':model,'judge_status':'COMPLETED' if j else ('ERROR' if error else 'MISSING_JUDGMENT'),'claim_supported':j.get('claim_supported') if j else None,'interaction_supported':j.get('interaction_supported') if j else None,'uncertainty_appropriate':j.get('uncertainty_appropriate') if j else None,'external_law_claim':j.get('external_law_claim') if j else None,'concerns':j.get('concerns',[]) if j else [],'judge_confidence':j.get('confidence') if j else None,'judge_rationale':j.get('rationale','') if j else '', 'exact_quote_exists_flags':exact,'exact_quote_count':sum(exact),'quote_count':len(evs),'all_quotes_exact':bool(evs) and all(exact),'elapsed_seconds_for_fixture_batch':elapsed,'prompt_sha256':ph,'error':error,'interpretation':'LLM-as-judge diagnostic only; not human gold or validated judge reliability'})
            checkpoint={'schema_version':1,'status':'RUNNING','created_at_utc':datetime.now(timezone.utc).isoformat(),'evaluation_type':'TWO_MODEL_LLM_AS_JUDGE_DIAGNOSTIC_NOT_GOLD','input_path':str(IN.relative_to(ROOT)),'input_sha256':sha(IN),'case_count':len(rows),'judge_models':MODELS,'judge_record_count':len(results),'prompt_sha256':prompt_hashes,'results':results,'checkpoint':True}
            OUT.write_text(json.dumps(checkpoint,indent=2,ensure_ascii=False),encoding='utf-8')
            print(f'[DONE] {fixture_type}/{model}: {sum(1 for r in group if judged.get(r["scenario_id"]))}/{len(group)} judgments, {elapsed}s'+(f' ERROR={error}' if error else ''),flush=True)
    fields=['claim_supported','interaction_supported','uncertainty_appropriate','external_law_claim']
    summaries={}
    for model in MODELS:
        rr=[x for x in results if x['model']==model]
        summaries[model]={'records':len(rr),'completed':sum(x['judge_status']=='COMPLETED' for x in rr),'missing_or_error':sum(x['judge_status']!='COMPLETED' for x in rr)}
        for field in fields:
            vals=[x[field] for x in rr if isinstance(x.get(field),bool)]
            summaries[model][field]={'true':sum(v is True for v in vals),'false':sum(v is False for v in vals),'null_or_missing':len(rr)-len(vals)}
        summaries[model]['all_quotes_exact_count']=sum(x['all_quotes_exact'] for x in rr)
        summaries[model]['positive_findings_with_quote_count']=sum(x['quote_count']>0 for x in rr)
    by_scenario={}
    for sid in sorted({x['scenario_id'] for x in results}):
        rr=[x for x in results if x['scenario_id']==sid]
        a=next((x for x in rr if x['model']==MODELS[0]),None);b=next((x for x in rr if x['model']==MODELS[1]),None)
        def pair(field):
            av=a.get(field) if a else None; bv=b.get(field) if b else None
            return (av == bv) if isinstance(av,bool) and isinstance(bv,bool) else None
        by_scenario[sid]={'judges_present':sum(x['judge_status']=='COMPLETED' for x in rr),'claim_supported_agree':pair('claim_supported'),'interaction_supported_agree':pair('interaction_supported'),'uncertainty_appropriate_agree':pair('uncertainty_appropriate')}
    report={'schema_version':1,'status':'COMPLETED' if all(x['judge_status']=='COMPLETED' for x in results) else 'PARTIAL','created_at_utc':datetime.now(timezone.utc).isoformat(),'evaluation_type':'TWO_MODEL_LLM_AS_JUDGE_DIAGNOSTIC_NOT_GOLD','input_path':str(IN.relative_to(ROOT)),'input_sha256':sha(IN),'input_refresh_note':input_refresh_note,'case_count':len(rows),'judge_models':MODELS,'judge_record_count':len(results),'summaries_by_model':summaries,'pairwise_agreement_counts':{f:{'comparable':sum(1 for v in by_scenario.values() if v['judges_present']==2 and isinstance(v[f+'_agree'],bool)),'agree':sum(1 for v in by_scenario.values() if v['judges_present']==2 and v[f+'_agree'] is True)} for f in ['claim_supported','interaction_supported','uncertainty_appropriate']},'prompt_sha256':prompt_hashes,'results':results,'limitations':['Judge labels are machine assessments, not human annotations or gold.','No human-calibrated probe set exists; inter-judge agreement is descriptive, not validated reliability.','Judges received source text and observed outputs, not expected statuses or authored scenario rationales.','Exact quote checks are deterministic substring checks; semantic entailment remains judge-assessed.']}
    OUT.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    lines=['# LLM-as-judge diagnostics — Phase 2','',f"- Status: {report['status']}",f"- Scenario cases: {len(rows)}",f"- Judge records: {len(results)}",'- This is a machine-assessed rubric diagnostic, **not** human gold, validated judge reliability, or legal-risk accuracy.','', '## Per-model summary','', '| Model | Completed | Claim supported (true/false) | Interaction supported (true/false) | Uncertainty appropriate (true/false) | All quotes exact |','|---|---:|---|---|---|---:|']
    for model,s in summaries.items():
        lines.append(f"| {model} | {s['completed']}/{s['records']} | {s['claim_supported']['true']}/{s['claim_supported']['false']} | {s['interaction_supported']['true']}/{s['interaction_supported']['false']} | {s['uncertainty_appropriate']['true']}/{s['uncertainty_appropriate']['false']} | {s['all_quotes_exact_count']}/{s['positive_findings_with_quote_count']} |")
    lines += ['', '## Descriptive pairwise agreement', '', '| Rubric field | Comparable scenarios | Agreement |','|---|---:|---:|']
    for f,v in report['pairwise_agreement_counts'].items():lines.append(f"| {f} | {v['comparable']} | {v['agree']}/{v['comparable']} |")
    lines += ['', '## Disagreements and concerns','']
    for sid in sorted(by_scenario):
        rr=[x for x in results if x['scenario_id']==sid]
        if any(x['judge_status']!='COMPLETED' or x['concerns'] or x['claim_supported'] is False or x['interaction_supported'] is False or x['uncertainty_appropriate'] is False for x in rr):
            lines.append(f"### {sid}")
            for x in rr: lines.append(f"- {x['model']}: status={x['judge_status']}; supported={x['claim_supported']}; interaction={x['interaction_supported']}; uncertainty={x['uncertainty_appropriate']}; exact quotes={x['all_quotes_exact']}; concerns={json.dumps(x['concerns'],ensure_ascii=False)}; rationale={x['judge_rationale']}")
            lines.append('')
    lines += ['## Provenance','',f"- Input SHA-256: `{report['input_sha256']}`"]
    if report.get('input_refresh_note'): lines.append('- Input refresh note: '+report['input_refresh_note'])
    lines += [f"- Prompt SHA-256 ({k}): `{v}`" for k,v in prompt_hashes.items()]+['']
    MD.write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({'status':report['status'],'cases':len(rows),'judge_records':len(results),'summaries':summaries,'agreement':report['pairwise_agreement_counts'],'json':str(OUT.relative_to(ROOT)),'markdown':str(MD.relative_to(ROOT))},indent=2))
if __name__=='__main__':raise SystemExit(main())

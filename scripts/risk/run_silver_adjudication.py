#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, json, re, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import requests

ROOT=Path(__file__).resolve().parents[2]

def ollama(model,prompt,num_ctx=8192,max_tokens=900,url='http://127.0.0.1:11434'):
    r=requests.post(url+'/api/generate',json={
      'model':model,'prompt':prompt,'stream':False,'think':False,
      'options':{'temperature':0,'num_ctx':num_ctx,'num_predict':max_tokens}
    },timeout=600)
    r.raise_for_status()
    return str(r.json().get('response','')).strip()

def parse_json(text):
    text=str(text or "").strip()
    try:
        value=json.loads(text)
        if isinstance(value,dict) and isinstance(value.get("cases"),list):
            return value
    except Exception:
        pass
    decoder=json.JSONDecoder()
    candidates=[]
    for match in re.finditer(r'\{', text):
        try:
            value,end=decoder.raw_decode(text[match.start():])
        except Exception:
            continue
        if isinstance(value,dict) and "cases" in value:
            candidates.append(value)
    valid=[x for x in candidates if isinstance(x.get("cases"),list)]
    if valid:
        return max(valid, key=lambda x: len(x.get("cases") or []))
    return None

def call_batch(model,prompt,expected_cases,url,max_attempts=3,max_tokens=700):
    last=None
    for attempt in range(1,max_attempts+1):
        try:
            raw=parse_json(ollama(model,prompt,max_tokens=max_tokens,url=url))
        except Exception:
            raw=None
        last=raw
        if isinstance(raw,dict) and isinstance(raw.get("cases"),list):
            ids=set()
            for x in raw["cases"]:
                if isinstance(x,dict) and str(x.get("case","")).isdigit():
                    ids.add(int(x["case"]))
            if set(range(expected_cases)).issubset(ids):
                return raw
        if attempt < max_attempts:
            time.sleep(0.2)
    return last

def normalize(x):
    x=x if isinstance(x,dict) else {}
    ans=str(x.get('risk') or x.get('answer') or 'UNCERTAIN').upper().strip()
    ans={'YES':'YES','NO':'NO','UNCERTAIN':'UNCERTAIN','UNKNOWN':'UNCERTAIN','DON\'T KNOW':'UNCERTAIN'}.get(ans,'UNCERTAIN')
    sev=str(x.get('severity') or x.get('risk_level') or '').upper().strip()
    if sev not in {'INFORMATIONAL','LOW','MEDIUM','HIGH','CRITICAL'}: sev=''
    evidence=str(x.get('evidence') or '').strip()
    risk_type=str(x.get('risk_type') or '').strip()
    reason=str(x.get('reason') or x.get('why') or '').strip()
    return {'risk':ans,'severity':sev,'risk_type':risk_type,'evidence':evidence,'reason':reason}

def judge_prompt(row,style):
    return f'''You are an independent commercial-contract risk annotator. This is NOT legal advice and NOT a probability judgment. The task is to label a clause against one explicit buyer-side risk predicate.

{style}

NON-NEGOTIABLE RULES:
- Use only the supplied contract clause as contract evidence.
- Treat the question as the risk predicate and the flag_if rule as the trigger.
- A YES risk label requires the predicate/flag condition to be supported by the contract text.
- A NO label means the supplied text supports that the risk condition is not present.
- If the text does not contain enough information to decide, use UNCERTAIN.
- Do not infer facts outside the clause (deal value, governing law, insurance limits, intent, industry practice).
- Do not turn a protective observation into risk unless the predicate explicitly asks for the risky condition.
- Mutual/reciprocal language is NOT one-sided unless the text actually differentiates the parties.
- Evidence must be an exact contiguous substring of the clause. For NO/UNCERTAIN, evidence may be empty.
- Severity is required only for YES. Use INFORMATIONAL/LOW/MEDIUM/HIGH/CRITICAL.
- Return JSON only.

CLAUSE TYPE: {row['clause_type']}
CHECK ID: {row['check_id']}
RISK QUESTION: {row['question']}
FLAG IF: {row['flag_if']}
CONTRACT CLAUSE:
{row['clause_text']}

Return:
{{"risk":"YES|NO|UNCERTAIN","risk_type":"concrete exposure or empty","severity":"INFORMATIONAL|LOW|MEDIUM|HIGH|CRITICAL|empty","evidence":"exact contiguous quote or empty","reason":"brief text-grounded reason"}}'''

def verify_prompt(row,first):
    return f'''Act as a skeptical verifier of a machine risk annotation. Re-evaluate the clause from scratch against the same risk predicate. Your job is to catch false positives, protective-vs-risk polarity errors, unsupported assumptions, and non-exact evidence.

Rules: use only the contract clause; obey QUESTION and FLAG IF; exact contiguous evidence for YES; use UNCERTAIN when the text is insufficient. Do not defer to the first annotation.

CLAUSE TYPE: {row['clause_type']}
CHECK ID: {row['check_id']}
QUESTION: {row['question']}
FLAG IF: {row['flag_if']}
CLAUSE:
{row['clause_text']}

FIRST ANNOTATION (may be wrong):
{json.dumps(first,ensure_ascii=False)}

Return JSON only:
{{"risk":"YES|NO|UNCERTAIN","risk_type":"concrete exposure or empty","severity":"INFORMATIONAL|LOW|MEDIUM|HIGH|CRITICAL|empty","evidence":"exact contiguous quote or empty","reason":"brief correction or confirmation"}}'''

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--queue',type=Path,default=ROOT/'data/risk/silver/silver_queue.csv')
    ap.add_argument('--out',type=Path,default=ROOT/'data/risk/silver/silver_annotations.csv')
    ap.add_argument('--judge-model',default='llama3.1:8b')
    ap.add_argument('--verifier-model',default='gemma3:12b')
    ap.add_argument('--judge-url',default='http://127.0.0.1:11435')
    ap.add_argument('--verifier-url',default='http://127.0.0.1:11436')
    ap.add_argument('--limit',type=int)
    ap.add_argument('--batch-size',type=int,default=3)
    ap.add_argument('--max-tokens',type=int,default=700)
    args=ap.parse_args()

    rows=list(csv.DictReader(args.queue.open(encoding='utf-8')))
    if args.limit:
        rows=rows[:args.limit]

    out_jsonl=args.out.with_suffix('.jsonl')
    args.out.parent.mkdir(parents=True,exist_ok=True)
    done={}
    if out_jsonl.exists():
        for line in out_jsonl.read_text(encoding='utf-8').splitlines():
            if line.strip():
                x=json.loads(line)
                done[x['sample_id']]=x

    pending=[r for r in rows if r['sample_id'] not in done]
    for start in range(0,len(pending),args.batch_size):
        batch=pending[start:start+args.batch_size]
        cases=[{
            'case':i,
            'clause_type':r['clause_type'],
            'check_id':r['check_id'],
            'question':r['question'],
            'flag_if':r['flag_if'],
            'clause':r['clause_text'][:3000],
        } for i,r in enumerate(batch)]

        prompt1='''You are an independent commercial-contract risk annotator. Evaluate each case against the explicit buyer-side risk condition defined by QUESTION + FLAG IF.

CRITICAL LABEL SEMANTICS:
- SILVER RISK=YES means the condition described by FLAG IF is satisfied by the supplied clause.
- SILVER RISK=NO means the FLAG IF condition is not satisfied.
- SILVER RISK=UNCERTAIN means the clause is insufficient to decide.
- Do NOT confuse the grammatical answer to QUESTION with the risk label. If FLAG IF says "No", absence of the feature can itself make RISK=YES. If FLAG IF says "None", absence of an exception can make RISK=YES.

Use only the supplied clause. Do not infer deal value, intent, governing law, industry practice, or facts outside the text. Mutual language is not one-sided. For YES, evidence must be an exact contiguous substring of the clause. Severity only for YES. Return JSON only: {"cases":[{"case":0,"risk":"YES|NO|UNCERTAIN","risk_type":"","severity":"","evidence":"","reason":""}]}. CASES:\n''' + json.dumps(cases,ensure_ascii=False)

        prompt2='''You are a skeptical independent verifier. Re-evaluate every case from scratch. You are an independent model and are blind to any first-model annotation.

CRITICAL LABEL SEMANTICS:
- SILVER RISK=YES means the FLAG IF condition is satisfied by the supplied clause.
- SILVER RISK=NO means the FLAG IF condition is not satisfied.
- SILVER RISK=UNCERTAIN means the clause is insufficient to decide.
- Do NOT answer the natural-language QUESTION mechanically; use FLAG IF to determine whether the condition is risky.

Catch polarity errors, false one-sidedness, unsupported assumptions, and invalid evidence. Use only the supplied clause. For YES, evidence must be an exact contiguous substring of the clause. Return JSON only: {"cases":[{"case":0,"risk":"YES|NO|UNCERTAIN","risk_type":"","severity":"","evidence":"","reason":""}]}. CASES:
''' + json.dumps(cases,ensure_ascii=False)

        # Judge and blind verifier are independent and therefore run concurrently.
        with ThreadPoolExecutor(max_workers=2) as ex:
            f1=ex.submit(call_batch,args.judge_model,prompt1,len(batch),args.judge_url,3,args.max_tokens)
            f2=ex.submit(call_batch,args.verifier_model,prompt2,len(batch),args.verifier_url,3,args.max_tokens)
            raw1=f1.result()
            raw2=f2.result()

        items1=(raw1 or {}).get('cases',[]) if isinstance(raw1,dict) else []
        items2=(raw2 or {}).get('cases',[]) if isinstance(raw2,dict) else []
        map1={int(x['case']):normalize(x) for x in items1 if isinstance(x,dict) and str(x.get('case','')).isdigit()}
        map2={int(x['case']):normalize(x) for x in items2 if isinstance(x,dict) and str(x.get('case','')).isdigit()}
        firsts=[map1.get(i,normalize({})) for i in range(len(batch))]
        with out_jsonl.open('a',encoding='utf-8') as fh:
            for i,row in enumerate(batch):
                a=firsts[i]; b=map2.get(i,normalize({}))
                ev_a=bool(a['evidence']) and a['evidence'] in row['clause_text']
                ev_b=bool(b['evidence']) and b['evidence'] in row['clause_text']
                if a['risk']==b['risk']:
                    final=a['risk']
                    status='MACHINE_AGREED' if final!='UNCERTAIN' else 'MACHINE_AGREED_UNCERTAIN'
                else:
                    final='UNCERTAIN'
                    status='MACHINE_DISAGREEMENT'
                if final=='YES' and not (ev_a and ev_b):
                    final='UNCERTAIN'
                    status='MACHINE_AGREED_BUT_EVIDENCE_INVALID'
                out={**row,
                     'silver_risk':final,
                     'silver_risk_type':(a['risk_type'] or b['risk_type']) if final=='YES' else '',
                     'silver_severity':(a['severity'] or b['severity']) if final=='YES' else '',
                     'silver_evidence':a['evidence'] if final=='YES' else '',
                     'silver_confidence':'HIGH' if status=='MACHINE_AGREED' and final!='UNCERTAIN' else 'LOW',
                     'silver_status':status,
                     'adjudication_method':f'{args.judge_model.upper()}_{args.verifier_model.upper()}_TWO_MODEL_CONSENSUS',
                     'judge_model':args.judge_model,
                     'verifier_model':args.verifier_model,
                     'max_tokens':args.max_tokens,
                     'judge_1':a,'judge_2':b,'protocol_version':'silver_v5_blind_parallel'}
                fh.write(json.dumps(out,ensure_ascii=False)+'\n')
                done[row['sample_id']]=out
                print(f"{start+i+1}/{len(pending)} {row['sample_id']} {row['check_id']} -> {final} [{status}]",flush=True)

    fields=['sample_id','annotation_partition','document_id','clause_index','clause_type','clause_text','check_id','question','flag_if','silver_risk','silver_risk_type','silver_severity','silver_evidence','silver_confidence','silver_status','adjudication_method','judge_model','verifier_model','max_tokens','protocol_version','notes']
    with args.out.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
        for x in done.values():
            w.writerow({k:x.get(k,'') for k in fields})
    print('WROTE',len(done),args.out)

if __name__=='__main__': main()

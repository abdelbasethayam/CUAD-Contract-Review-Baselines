#!/usr/bin/env python3
from __future__ import annotations
import csv, hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'data/splits/test/master_clauses_test.csv'
OUT=ROOT/'data/risk/external/cuad_test_presence_gold.csv'
META=ROOT/'data/risk/external/cuad_test_presence_gold.manifest.json'
METADATA={'Document Name','Parties','Agreement Date','Effective Date','Expiration Date'}
rows=[]
with SOURCE.open(encoding='utf-8-sig',newline='') as f:
    for r in csv.DictReader(f):
        if str(r.get('is_metadata','')).lower()=='true' or r.get('clause_type') in METADATA:
            continue
        answer=str(r.get('answer') or '').strip()
        text=str(r.get('clause_text') or '').strip()
        if not text:
            continue
        rows.append({
            'document_id':str(r.get('document_id') or ''),
            'clause_type':str(r.get('clause_type') or ''),
            'clause_text':text,
            'cuad_answer':answer,
            'expert_clause_present':'YES' if answer else 'NO',
            'ground_truth_status':'CUAD_EXPERT_DERIVED_PRESENCE',
            'risk_gold_status':'NOT_RISK_GOLD',
        })
OUT.parent.mkdir(parents=True,exist_ok=True)
with OUT.open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
sha=hashlib.sha256(OUT.read_bytes()).hexdigest()
docs=sorted({r['document_id'] for r in rows})
cats=sorted({r['clause_type'] for r in rows})
meta={
 'schema_version':1,
 'source_path':str(SOURCE),
 'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
 'output_sha256':sha,
 'contract_count':len(docs),
 'row_count':len(rows),
 'category_count':len(cats),
 'categories':cats,
 'positive_rows':sum(r['expert_clause_present']=='YES' for r in rows),
 'ground_truth':'CUAD expert-derived human annotation; clause presence only',
 'scope_note':'This is an expert-derived external/held-out presence benchmark. It is NOT ground truth for the custom 37-target buyer-side risk predicates, severity, or risk type.',
}
META.write_text(json.dumps(meta,indent=2),encoding='utf-8')
print(json.dumps(meta,indent=2))

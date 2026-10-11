#!/usr/bin/env python3
from __future__ import annotations
import csv, json, hashlib, sys
from pathlib import Path
from qdrant_client import QdrantClient
ROOT=Path(__file__).resolve().parents[2]
def docs_csv(p):
    with p.open(encoding='utf-8-sig',newline='') as f: return [r for r in csv.DictReader(f)]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
tr=docs_csv(ROOT/'data/splits/train/master_clauses_train.csv')
te=docs_csv(ROOT/'data/splits/test/master_clauses_test.csv')
train_docs={r['document_id'] for r in tr}; test_docs={r['document_id'] for r in te}
checks=[]
checks.append(('train_test_contract_overlap', len(train_docs & test_docs)==0, len(train_docs & test_docs)))
gold=docs_csv(ROOT/'data/risk/gold/annotation_queue.csv')
parts={p:{r['document_id'] for r in gold if r.get('annotation_partition')==p} for p in ('calibration','development','locked_test')}
checks.append(('gold_uses_train_docs_only', all(s<=train_docs for s in parts.values()), sum(len(s-train_docs) for s in parts.values())))
checks.append(('gold_partition_disjoint', not(parts['calibration']&parts['development'] or parts['calibration']&parts['locked_test'] or parts['development']&parts['locked_test']), 0))
silver=docs_csv(ROOT/'data/risk/silver/silver_queue.csv')
silver_docs={r['document_id'] for r in silver}
checks.append(('silver_uses_test_docs_only', silver_docs<=test_docs, len(silver_docs-test_docs)))
checks.append(('silver_train_overlap', not(silver_docs&train_docs), len(silver_docs&train_docs)))
# Expert presence gold must derive only from held-out test.
eg=ROOT/'data/risk/external/cuad_test_presence_gold.csv'
if eg.exists():
    egr=docs_csv(eg); ed={r['document_id'] for r in egr}
    checks.append(('expert_presence_uses_test_docs_only', ed<=test_docs, len(ed-test_docs)))
# Local Qdrant contract collections must contain training docs only.
client=QdrantClient(path=str(ROOT/'data/qdrant_local'))
for name in ('cuad_train','cuad_train_mpnet','cuad_train_hashing'):
    if client.collection_exists(name):
        seen=set(); off=None
        while True:
            pts, off=client.scroll(collection_name=name,limit=512,offset=off,with_payload=['document_id'])
            seen.update(str((p.payload or {}).get('document_id','')) for p in pts)
            if off is None: break
        checks.append((name+'_payload_train_only', seen<=train_docs, len(seen-train_docs)))
        checks.append((name+'_payload_test_overlap', not(seen&test_docs), len(seen&test_docs)))
report={'checks':[{'name':n,'passed':bool(ok),'value':v} for n,ok,v in checks],
        'train_contracts':len(train_docs),'test_contracts':len(test_docs),
        'train_rows':len(tr),'test_rows':len(te)}
out=ROOT/'data/risk/EVALUATION_INTEGRITY_REPORT.json'
out.write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
if not all(x[1] for x in checks): sys.exit(2)

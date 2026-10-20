#!/usr/bin/env python3
"""Verify extracted server result snapshots against the committed SHA-256 manifest."""
import argparse, hashlib, json, sys
from pathlib import Path

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('extracted_root', type=Path)
    ap.add_argument('manifest', type=Path)
    args=ap.parse_args()
    manifest=json.loads(args.manifest.read_text(encoding='utf-8'))
    errors=[]
    for item in manifest['results']:
        p=args.extracted_root/item['run_id']/'result.json'
        if not p.is_file():
            errors.append(f"MISSING {item['run_id']}/result.json")
            continue
        raw=p.read_bytes(); actual=hashlib.sha256(raw).hexdigest()
        if actual != item['sha256']:
            errors.append(f"HASH MISMATCH {item['run_id']}: expected {item['sha256']} got {actual}")
        else:
            print(f"OK {item['run_id']} {actual}")
    if errors:
        print('\n'.join(errors), file=sys.stderr); return 1
    print(f"Verified {len(manifest['results'])} result files; all SHA-256 hashes match.")
    return 0
if __name__=='__main__': raise SystemExit(main())

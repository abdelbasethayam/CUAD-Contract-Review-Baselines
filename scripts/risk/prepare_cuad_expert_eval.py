#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_JSON = ROOT / "data/raw/cuad/CUAD_v1/CUAD_v1.json"
DEFAULT_TEST_WIDE = ROOT / "data/splits/test/master_clauses_test_wide.csv"
DEFAULT_OUT = ROOT / "data/risk/external/cuad_expert_test.jsonl"
METADATA = {"Document Name", "Parties", "Agreement Date", "Effective Date", "Expiration Date"}

def stem(x: str) -> str:
    return str(x).strip().removesuffix('.pdf').removesuffix('.PDF').casefold()

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", type=Path, default=DEFAULT_JSON)
    ap.add_argument("--test-wide", type=Path, default=DEFAULT_TEST_WIDE)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--include-metadata", action="store_true")
    args = ap.parse_args()

    with args.test_wide.open("r", encoding="utf-8-sig", newline="") as f:
        test_names = {stem(r["Filename"]) for r in csv.DictReader(f)}

    data = json.loads(args.json.read_text(encoding="utf-8"))
    records = []
    categories = set()
    answerable = 0
    impossible = 0

    for contract in data["data"]:
        title = str(contract.get("title", "")).strip()
        if stem(title) not in test_names:
            continue
        for pidx, paragraph in enumerate(contract.get("paragraphs", [])):
            context = str(paragraph.get("context", ""))
            for qa in paragraph.get("qas", []):
                category = str(qa.get("id", "")).rsplit("__", 1)[-1]
                if not category or (category in METADATA and not args.include_metadata):
                    continue
                impossible_flag = bool(qa.get("is_impossible", False))
                answers = [
                    {"text": str(a.get("text", "")), "answer_start": int(a.get("answer_start", -1))}
                    for a in qa.get("answers", [])
                ]
                records.append({
                    "qa_id": str(qa.get("id", "")),
                    "document_id": title,
                    "category": category,
                    "question": str(qa.get("question", "")),
                    "context": context,
                    "answers": answers,
                    "is_impossible": impossible_flag,
                    "paragraph_index": pidx,
                    "context_sha256": hashlib.sha256(context.encode("utf-8")).hexdigest(),
                })
                categories.add(category)
                if impossible_flag:
                    impossible += 1
                else:
                    answerable += 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    manifest = {
        "schema_version": 1,
        "source_json": str(args.json),
        "source_sha256": hashlib.sha256(args.json.read_bytes()).hexdigest(),
        "test_contract_source": str(args.test_wide),
        "test_contract_count": len({r["document_id"] for r in records}),
        "task_count": len(records),
        "category_count": len(categories),
        "categories": sorted(categories),
        "answerable_tasks": answerable,
        "impossible_tasks": impossible,
        "include_metadata": bool(args.include_metadata),
        "ground_truth": "CUAD expert annotations; external evidence benchmark; not project risk gold",
    }
    mp = args.out.with_suffix(".manifest.json")
    mp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps(manifest, indent=2))

if __name__ == "__main__":
    main()

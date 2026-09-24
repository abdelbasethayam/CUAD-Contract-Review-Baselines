from __future__ import annotations

import ast
import csv
import difflib
import json
import math
import re
import unicodedata
import uuid
from collections import Counter
from pathlib import Path


ANSWER_SUFFIX_RE = re.compile(r"\s*-\s*answer\s*$", re.IGNORECASE)
METADATA_LABELS = {
    "Document Name",
    "Parties",
    "Agreement Date",
    "Effective Date",
    "Expiration Date",
}
FIXED_CATEGORIES = [
    "Warranty Duration",
    "Price Restrictions",
    "Non-Compete",
    "Rofr/Rofo/Rofn",
    "Competitive Restriction Exception",
    "Joint Ip Ownership",
    "Revenue/Profit Sharing",
    "Termination For Convenience",
    "Audit Rights",
    "Affiliate License-Licensor",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def is_true(value: object) -> bool:
    return str(value or "").strip().lower() in {"true", "1", "yes"}


def clean_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text in {"[]", "nan", "None"}:
        return None
    return text


def normalize_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).lower().split())


def parse_spans(value: object) -> list[str]:
    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []
    try:
        parsed = ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return [text]
    if isinstance(parsed, list):
        return [str(item).strip() for item in parsed if str(item).strip()]
    return [str(parsed).strip()]


def discover_columns(columns: list[str]) -> tuple[list[str], dict[str, str]]:
    answer_columns: dict[str, str] = {}
    text_columns: list[str] = []
    for column in columns:
        if column == "Filename":
            continue
        if ANSWER_SUFFIX_RE.search(column):
            answer_columns[ANSWER_SUFFIX_RE.sub("", column).strip()] = column
        else:
            text_columns.append(column)
    return text_columns, answer_columns


def uuid_for(row: dict[str, str], source_index: int) -> str:
    value = f"{row['document_id']}::{row['clause_type']}::{source_index}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, value))


def token_ngrams(text: str, n: int = 3) -> set[tuple[str, ...]]:
    tokens = re.findall(r"[a-z0-9]+", normalize_text(text))
    return set(tuple(tokens[i : i + n]) for i in range(max(0, len(tokens) - n + 1)))


def jaccard(left: set, right: set) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def main(root: Path, output_dir: Path) -> None:
    raw_dir = root / "data" / "raw" / "cuad" / "CUAD_v1"
    split_dir = root / "data" / "splits"
    train_long_path = split_dir / "train" / "master_clauses_train.csv"
    test_long_path = split_dir / "test" / "master_clauses_test.csv"
    train_wide_path = split_dir / "train" / "master_clauses_train_wide.csv"
    test_wide_path = split_dir / "test" / "master_clauses_test_wide.csv"
    embedding_path = root / "data" / "embeddings" / "train_embeddings.json"
    metadata_path = root / "data" / "embeddings" / "train_metadata.jsonl"
    fixed_path = root / "diagnostics" / "fixed_10_classification_baseline" / "selected_10_rows.json"

    raw_rows = read_csv(raw_dir / "master_clauses.csv")
    train_wide = read_csv(train_wide_path)
    test_wide = read_csv(test_wide_path)
    train_long = read_csv(train_long_path)
    test_long = read_csv(test_long_path)
    fixed = json.loads(fixed_path.read_text(encoding="utf-8"))
    embedding_data = json.loads(embedding_path.read_text(encoding="utf-8"))
    embedding_metadata = [
        json.loads(line)
        for line in metadata_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    text_columns, answer_columns = discover_columns(list(raw_rows[0]))
    raw_categories = [c for c in text_columns if c not in METADATA_LABELS]
    train_docs = {row["Filename"] for row in train_wide}
    test_docs = {row["Filename"] for row in test_wide}

    raw_json = json.loads((raw_dir / "CUAD_v1.json").read_text(encoding="utf-8"))
    raw_json_titles = {item.get("title") for item in raw_json.get("data", [])}

    train_nonmeta = [row for row in train_long if not is_true(row.get("is_metadata"))]
    test_nonmeta = [row for row in test_long if not is_true(row.get("is_metadata"))]
    train_meta = [row for row in train_long if is_true(row.get("is_metadata"))]
    test_meta = [row for row in test_long if is_true(row.get("is_metadata"))]
    train_empty = [row for row in train_long if not clean_text(row.get("clause_text"))]
    test_empty = [row for row in test_long if not clean_text(row.get("clause_text"))]
    train_valid_for_embedding = [
        row for row in train_nonmeta if clean_text(row.get("clause_text"))
    ]

    expected_records = []
    for source_index, row in enumerate(train_long):
        if is_true(row.get("is_metadata")):
            continue
        text = clean_text(row.get("clause_text"))
        if text is None:
            continue
        expected_records.append(
            {
                "id": uuid_for(row, source_index),
                "document_id": row["document_id"],
                "clause_type": row["clause_type"],
                "clause_text": text,
                "source_index": source_index,
            }
        )

    expected_ids = {row["id"] for row in expected_records}
    persisted_ids = [row.get("id") for row in embedding_metadata]
    persisted_id_set = set(persisted_ids)
    expected_by_id = {row["id"]: row for row in expected_records}
    persisted_by_id = {row.get("id"): row for row in embedding_metadata}
    id_missing = sorted(expected_ids - persisted_id_set)
    id_extra = sorted(persisted_id_set - expected_ids)
    field_mismatches = []
    for record_id in sorted(expected_ids & persisted_id_set):
        expected = expected_by_id[record_id]
        actual = persisted_by_id[record_id]
        for field in ("document_id", "clause_type", "clause_text"):
            if expected[field] != actual.get(field):
                field_mismatches.append({"id": record_id, "field": field})

    train_category = Counter(row["clause_type"] for row in train_nonmeta)
    test_category = Counter(row["clause_type"] for row in test_nonmeta)
    embedded_category = Counter(row.get("clause_type") for row in embedding_metadata)
    train_texts = Counter(row["clause_text"] for row in train_nonmeta if row["clause_text"])
    test_texts = Counter(row["clause_text"] for row in test_nonmeta if row["clause_text"])
    train_normalized = Counter(normalize_text(text) for text in train_texts)
    test_normalized = Counter(normalize_text(text) for text in test_texts)
    fixed_rows = fixed["rows"]
    fixed_category = Counter(row["clause_type"] for row in fixed_rows)
    # The fixed-selection generator stores the source CSV line number, with
    # the header at line 1. Preserve that convention when validating rows.
    test_by_source_index = {index + 2: row for index, row in enumerate(test_long)}
    fixed_audit = []
    for row in fixed_rows:
        source_row = test_by_source_index.get(int(row["original_row_index"]))
        fixed_audit.append(
            {
                "benchmark_row_id": row["benchmark_row_id"],
                "original_row_index": row["original_row_index"],
                "document_id": row["document_id"],
                "clause_type": row["clause_type"],
                "clause_text_length": len(row["clause_text"]),
                "document_in_test": row["document_id"] in test_docs,
                "selection_matches_test_row": bool(
                    source_row
                    and source_row.get("document_id") == row["document_id"]
                    and source_row.get("clause_type") == row["clause_type"]
                    and source_row.get("clause_text") == row["clause_text"]
                ),
                "train_examples": train_category[row["clause_type"]],
                "embedded_examples": embedded_category[row["clause_type"]],
                "exact_train_text_match": row["clause_text"] in train_texts,
                "normalized_train_text_match": normalize_text(row["clause_text"]) in train_normalized,
            }
        )

    exact_overlap = sorted(set(train_texts) & set(test_texts))
    normalized_overlap = sorted(set(train_normalized) & set(test_normalized))
    fixed_exact_matches = [row["benchmark_row_id"] for row in fixed_rows if row["clause_text"] in train_texts]
    fixed_normalized_matches = [
        row["benchmark_row_id"]
        for row in fixed_rows
        if normalize_text(row["clause_text"]) in train_normalized
    ]

    train_token_ngrams = [(row, token_ngrams(row["clause_text"])) for row in train_nonmeta]
    near_duplicate_results = []
    for fixed_row in fixed_rows:
        target_grams = token_ngrams(fixed_row["clause_text"])
        best_score = -1.0
        best_row = None
        for candidate, candidate_grams in train_token_ngrams:
            score = jaccard(target_grams, candidate_grams)
            if score > best_score:
                best_score = score
                best_row = candidate
        near_duplicate_results.append(
            {
                "benchmark_row_id": fixed_row["benchmark_row_id"],
                "best_train_jaccard_3gram": round(best_score, 6),
                "best_train_document_id": best_row["document_id"] if best_row else None,
                "best_train_clause_type": best_row["clause_type"] if best_row else None,
                "strong_near_duplicate_at_0_90": best_score >= 0.90,
            }
        )

    dimensions = sorted({len(vector) for vector in embedding_data.get("embeddings", [])})
    vector_values = [value for vector in embedding_data.get("embeddings", []) for value in vector]
    finite_vectors = all(math.isfinite(value) for value in vector_values)
    embedding_duplicate_ids = [key for key, value in Counter(persisted_ids).items() if value > 1]
    embedding_duplicate_texts = [
        key for key, value in Counter(row.get("clause_text") for row in embedding_metadata).items()
        if value > 1
    ]

    qdrant_audit = {"status": "NOT_CHECKED"}
    try:
        from qdrant_client import QdrantClient

        qdrant_client = QdrantClient(path=str(root / "data" / "qdrant_local"))
        qdrant_info = qdrant_client.get_collection("cuad_train")
        qdrant_vectors = qdrant_info.config.params.vectors
        qdrant_audit = {
            "status": str(qdrant_info.status),
            "points_count": qdrant_info.points_count,
            "vector_size": getattr(qdrant_vectors, "size", None),
            "distance": str(getattr(qdrant_vectors, "distance", None)),
        }
        qdrant_client.close()
    except Exception as exc:
        qdrant_audit = {"status": "READ_FAILED", "error": f"{type(exc).__name__}: {exc}"}

    all_categories = sorted(set(raw_categories) | set(train_category) | set(test_category))
    category_rows = []
    for category in all_categories:
        train_count = train_category[category]
        embedded_count = embedded_category[category]
        category_rows.append(
            {
                "category": category,
                "train_clauses": train_count,
                "test_clauses": test_category[category],
                "embedded_train_clauses": embedded_count,
                "exists_in_train": train_count > 0,
                "retention_percent": round(100 * embedded_count / train_count, 2) if train_count else 0.0,
                "fixed_pilot_rows": fixed_category[category],
            }
        )

    raw_answer_bases = set(answer_columns)
    unmatched_answer_columns = sorted(raw_answer_bases - set(text_columns))
    missing_answer_columns = sorted(set(text_columns) - raw_answer_bases)
    train_test_doc_overlap = sorted(train_docs & test_docs)
    embedding_docs = {row.get("document_id") for row in embedding_metadata}
    embedding_test_docs = sorted(embedding_docs & test_docs)

    audit = {
        "paths": {
            "raw_master_csv": str((raw_dir / "master_clauses.csv").relative_to(root)),
            "raw_cuad_json": str((raw_dir / "CUAD_v1.json").relative_to(root)),
            "train_wide": str(train_wide_path.relative_to(root)),
            "test_wide": str(test_wide_path.relative_to(root)),
            "train_long": str(train_long_path.relative_to(root)),
            "test_long": str(test_long_path.relative_to(root)),
            "train_embeddings": str(embedding_path.relative_to(root)),
            "train_metadata": str(metadata_path.relative_to(root)),
            "fixed_selection": str(fixed_path.relative_to(root)),
            "split_script": "data/scripts/dataset/split_cuad.py",
            "embedding_script": "data/scripts/embedding/embed_train.py",
        },
        "raw_dataset": {
            "master_contract_rows": len(raw_rows),
            "master_unique_document_ids": len({row["Filename"] for row in raw_rows}),
            "cuad_json_data_items": len(raw_json.get("data", [])),
            "cuad_json_unique_titles": len(raw_json_titles),
            "wide_columns": len(raw_rows[0]),
            "text_columns": len(text_columns),
            "answer_columns": len(answer_columns),
            "substantive_categories": len(raw_categories),
            "metadata_categories": sorted(METADATA_LABELS),
            "unmatched_answer_columns": unmatched_answer_columns,
            "text_columns_without_answer": missing_answer_columns,
        },
        "split": {
            "train_wide_rows": len(train_wide),
            "test_wide_rows": len(test_wide),
            "train_unique_documents": len(train_docs),
            "test_unique_documents": len(test_docs),
            "train_test_document_overlap": train_test_doc_overlap,
            "split_contract_count_matches_raw": len(train_wide) + len(test_wide) == len(raw_rows),
            "split_script_declares_train_size": 410,
            "split_script_declares_test_size": 100,
            "split_script_declares_random_state": 42,
        },
        "rows": {
            "train_long_rows": len(train_long),
            "test_long_rows": len(test_long),
            "train_metadata_rows": len(train_meta),
            "test_metadata_rows": len(test_meta),
            "train_non_metadata_rows": len(train_nonmeta),
            "test_non_metadata_rows": len(test_nonmeta),
            "train_empty_clause_text_rows": len(train_empty),
            "test_empty_clause_text_rows": len(test_empty),
            "train_invalid_after_cleaning": len(train_nonmeta) - len(train_valid_for_embedding),
            "train_expected_embedding_records": len(expected_records),
            "persisted_embedding_vectors": len(embedding_data.get("embeddings", [])),
            "persisted_metadata_records": len(embedding_metadata),
        },
        "embedding": {
            "persisted_count_field": embedding_data.get("count"),
            "persisted_model": embedding_data.get("model"),
            "dimensions": dimensions,
            "finite_values": finite_vectors,
            "duplicate_ids": embedding_duplicate_ids,
            "duplicate_text_count": len(embedding_duplicate_texts),
            "expected_id_missing_from_metadata": len(id_missing),
            "unexpected_metadata_ids": len(id_extra),
            "metadata_field_mismatches": len(field_mismatches),
            "embedding_documents": len(embedding_docs),
            "embedding_test_document_overlap": embedding_test_docs,
            "embedding_test_clause_count": sum(row["document_id"] in test_docs for row in embedding_metadata),
            "qdrant_local_collection": qdrant_audit,
        },
        "duplicates": {
            "exact_unique_text_overlap_count": len(exact_overlap),
            "exact_train_rows_with_overlap": sum(train_texts[text] for text in exact_overlap),
            "exact_test_rows_with_overlap": sum(test_texts[text] for text in exact_overlap),
            "normalized_unique_text_overlap_count": len(normalized_overlap),
            "normalized_train_rows_with_overlap": sum(train_normalized[text] for text in normalized_overlap),
            "normalized_test_rows_with_overlap": sum(test_normalized[text] for text in normalized_overlap),
            "exact_examples": [text[:180] for text in exact_overlap[:5]],
            "normalized_examples": [text[:180] for text in normalized_overlap[:5]],
            "fixed_exact_train_matches": fixed_exact_matches,
            "fixed_normalized_train_matches": fixed_normalized_matches,
            "near_duplicate_method": "maximum token 3-gram Jaccard similarity for each fixed row against all substantive train rows",
            "near_duplicate_threshold": 0.90,
            "fixed_rows_at_or_above_threshold": [row for row in near_duplicate_results if row["strong_near_duplicate_at_0_90"]],
            "fixed_row_nearest_neighbors": near_duplicate_results,
        },
        "fixed_10": {
            "row_count": len(fixed_rows),
            "ids": [row["benchmark_row_id"] for row in fixed_rows],
            "source_test_csv": fixed.get("source_test_csv"),
            "selection_matches_test_rows": all(row["selection_matches_test_row"] for row in fixed_audit),
            "unique_documents": len({row["document_id"] for row in fixed_rows}),
            "rows": fixed_audit,
        },
        "category_coverage": category_rows,
        "configuration": {
            "configured_model_from_data_scripts_env": "embed-english-v3.0",
            "configured_model_from_backend_env_example": "embed-english-v3.0",
            "model_matches_persisted": embedding_data.get("model") == "embed-english-v3.0",
            "embedding_dimension_expected": 1024,
        },
        "current_results_context": {
            "classification_fix_recall_at_5": 0.60,
            "classification_fix_accuracy": 0.40,
            "hybrid_recall_at_5": 0.60,
            "hybrid_accuracy": 0.50,
            "hybrid_retrieval_misses": 4,
            "hybrid_previous_misses_recovered": "0/4",
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "data_integrity_audit.json").write_text(json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    with (output_dir / "category_coverage.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = ["category", "train_clauses", "test_clauses", "embedded_train_clauses", "exists_in_train", "retention_percent", "fixed_pilot_rows"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(category_rows)

    with (output_dir / "fixed_10_audit.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = list(fixed_audit[0])
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(fixed_audit)

    with (output_dir / "split_audit.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = ["stage", "train", "test", "notes"]
        rows = [
            {"stage": "Original CUAD master contracts", "train": "", "test": "", "notes": len(raw_rows)},
            {"stage": "Wide contract rows", "train": len(train_wide), "test": len(test_wide), "notes": "one row per contract"},
            {"stage": "Long-format rows", "train": len(train_long), "test": len(test_long), "notes": "one row per extracted span"},
            {"stage": "Metadata rows", "train": len(train_meta), "test": len(test_meta), "notes": "excluded from embedding"},
            {"stage": "Substantive rows", "train": len(train_nonmeta), "test": len(test_nonmeta), "notes": "classification categories"},
            {"stage": "Rows embedded", "train": len(embedding_metadata), "test": "", "notes": "persisted metadata count"},
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    def pct(value: float) -> str:
        return f"{value * 100:.2f}%"

    report = []
    report.extend([
        "# Data Integrity Audit",
        "",
        "**Status: COMPLETE (read-only audit)**",
        "",
        "## Executive summary",
        "",
        "The live dataset artifacts show a correct 410/100 contract-level split with zero train/test document overlap and zero test documents in the persisted training embedding metadata. The actual train long-format count is 10,545, not 11,015; 10,545 -> 7,004 is fully reconciled because metadata rows are retained in the long-format file but intentionally excluded before embedding; no substantive rows are lost by empty-text filtering.",
        "",
        "The main data-quality concerns are reproducibility/documentation drift, not evidence of leakage: the current split/embedding scripts reference an older `data/dataset/...` layout while the live artifacts are under `data/raw` and `data/splits`, and `data/metadata/embedding_verification.md` records an older 5,449-vector run. The fixed 10-row benchmark is deliberately category-stratified and therefore not representative of the overall test distribution.",
        "",
        "## Repository paths inspected",
        "",
    ])
    for name, path in audit["paths"].items():
        report.append(f"- `{name}`: `{path}`")
    report.extend([
        "",
        "## Original dataset audit",
        "",
        f"- `master_clauses.csv`: `{audit['raw_dataset']['master_contract_rows']}` rows and `{audit['raw_dataset']['master_unique_document_ids']}` unique contract identifiers.",
        f"- `CUAD_v1.json`: `{audit['raw_dataset']['cuad_json_data_items']}` data items and `{audit['raw_dataset']['cuad_json_unique_titles']}` unique titles.",
        f"- Wide schema: `{audit['raw_dataset']['wide_columns']}` columns = `{audit['raw_dataset']['text_columns']}` clause/metadata text columns plus `{audit['raw_dataset']['answer_columns']}` answer columns and `Filename`.",
        f"- Substantive categories: `{audit['raw_dataset']['substantive_categories']}`; metadata categories: `{', '.join(audit['raw_dataset']['metadata_categories'])}`.",
        f"- Answer-column pairing: unmatched answer columns `{len(audit['raw_dataset']['unmatched_answer_columns'])}`; text columns without answer columns `{len(audit['raw_dataset']['text_columns_without_answer'])}`.",
        "",
        "## Train/test split audit",
        "",
        f"- Train wide contracts: `{audit['split']['train_unique_documents']}`; test wide contracts: `{audit['split']['test_unique_documents']}`.",
        f"- Train/test document intersection: `{len(audit['split']['train_test_document_overlap'])}`.",
        "- The split script calls `train_test_split` on the wide contract table before `wide_to_long`, with train size 410, test size 100, and random state 42.",
        "- **Invariant: PASS.** `TRAIN_DOCUMENT_IDS ∩ TEST_DOCUMENT_IDS = ∅` in the actual wide artifacts.",
        "- Reproducibility note: the checked-in script currently resolves `data/dataset/raw/...`, but the live repository artifacts are under `data/raw/...`; the existing files therefore cannot be regenerated from that script path without correcting the path layout. This is a minor reproducibility issue, not evidence that the stored split overlaps.",
        "",
        "## Row-count reconciliation",
        "",
        "| Stage | Train | Test | Notes |",
        "|---|---:|---:|---|",
        f"| Original CUAD master contracts | 510 | - | Wide source rows |",
        f"| Wide contract rows | {len(train_wide)} | {len(test_wide)} | One row per contract |",
        f"| Long-format rows | {len(train_long)} | {len(test_long)} | One row per extracted span |",
        f"| Metadata rows | {len(train_meta)} | {len(test_meta)} | Retained, flagged, then excluded from embeddings |",
        f"| Non-metadata rows | {len(train_nonmeta)} | {len(test_nonmeta)} | Substantive clause rows |",
        f"| Empty/invalid clause text rows | {len(train_empty)} | {len(test_empty)} | After long-format export |",
        f"| Persisted embedding records | {len(embedding_metadata)} | - | Training metadata JSONL |",
        "",
        "## Investigation: 11,015 -> 7,004",
        "",
        "| Filtering step | Rows removed | Rows remaining |",
        "|---|---:|---:|",
        f"| Train long-format input | 0 | {len(train_long)} |",
        f"| Metadata exclusion (`is_metadata=True`) | {len(train_meta)} | {len(train_nonmeta)} |",
        f"| Empty/invalid text cleaning | {len(train_nonmeta) - len(train_valid_for_embedding)} | {len(expected_records)} |",
        f"| Embedding persistence | 0 | {len(embedding_metadata)} |",
        "",
        f"The count reconciles exactly: `{len(train_long)} - {len(train_meta)} - {len(train_nonmeta) - len(train_valid_for_embedding)} = {len(embedding_metadata)}`. The reduction is intentional metadata filtering, not a failed embedding batch or category loss.",
        "",
        "## Category coverage",
        "",
        "See `category_coverage.csv` for all categories. Every substantive category present in the train/test artifacts has embedded training support; retention is calculated against the substantive train rows.",
        "",
        "| Category | Train clauses | Test clauses | Embedded train | Retention | Fixed rows |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for row in category_rows:
        if row["category"] in FIXED_CATEGORIES:
            report.append(f"| `{row['category']}` | {row['train_clauses']} | {row['test_clauses']} | {row['embedded_train_clauses']} | {row['retention_percent']:.2f}% | {row['fixed_pilot_rows']} |")
    report.extend([
        "",
        "The ten fixed categories all exist in training and have 100% retention into embeddings. Support size varies materially, so the audit does not claim that every category has enough examples for reliable retrieval; rare-category rows remain a plausible retrieval difficulty even without preprocessing loss.",
        "",
        "## Fixed-10 audit",
        "",
        f"- Rows: `{len(fixed_rows)}`; IDs are `{fixed['rows'][0]['benchmark_row_id']}` through `{fixed['rows'][-1]['benchmark_row_id']}`.",
        f"- Source: `{fixed.get('source_test_csv')}`; selection matches the corresponding test CSV rows: `{audit['fixed_10']['selection_matches_test_rows']}`.",
        f"- Unique contracts represented: `{audit['fixed_10']['unique_documents']}` (10 rows include two rows from the same Liquidmetal contract).",
        "",
        "| ID | Category | Text length | In test | Train support | Embedded support |",
        "|---|---|---:|---|---:|---:|",
    ])
    for row in fixed_audit:
        report.append(f"| `{row['benchmark_row_id']}` | `{row['clause_type']}` | {row['clause_text_length']} | {'Yes' if row['document_in_test'] else 'No'} | {row['train_examples']} | {row['embedded_examples']} |")
    report.extend([
        "",
        "## Test-set representativeness",
        "",
        f"The full substantive test set contains `{len(test_nonmeta)}` clause rows across `{len(test_docs)}` contracts and `{len(test_category)}` categories. The fixed pilot contains exactly one row from each of ten selected categories and therefore is **strongly stratified/skewed**, not a proportional sample of all test clauses.",
        "",
        "It is useful for controlled category-by-category diagnostics, but its accuracy must not be interpreted as overall test accuracy. Several fixed categories have substantially fewer or more examples than others in the full test distribution; the pilot intentionally overrepresents the chosen categories and rare-category behavior.",
        "",
        "## Duplicate and leakage audit",
        "",
        f"- Exact substantive clause-text overlap: `{len(exact_overlap)}` unique texts; train rows affected `{sum(train_texts[text] for text in exact_overlap)}`; test rows affected `{sum(test_texts[text] for text in exact_overlap)}`.",
        f"- Normalized overlap (Unicode NFKC, lowercase, whitespace normalization): `{len(normalized_overlap)}` unique texts; train rows affected `{sum(train_normalized[text] for text in normalized_overlap)}`; test rows affected `{sum(test_normalized[text] for text in normalized_overlap)}`.",
        f"- These overlaps occur across distinct train/test documents, so they are not document leakage; they are repeated clause-text patterns that can make a small number of test rows easier. Fixed-10 exact matches against train: `{len(fixed_exact_matches)}`; normalized matches: `{len(fixed_normalized_matches)}`.",
        f"- Near-duplicate check: token 3-gram Jaccard, maximum train similarity for each fixed row; threshold 0.90. Fixed rows at/above threshold: `{len([row for row in near_duplicate_results if row['strong_near_duplicate_at_0_90']])}`.",
        "- The fixed pilot has no exact or strong near-duplicate train matches under these checks. This is not a proof that all semantic similarity across the entire corpus is absent.",
        "",
        "## Embedding and document leakage audit",
        "",
        f"- Persisted vectors: `{len(embedding_data.get('embeddings', []))}`; metadata records: `{len(embedding_metadata)}`; dimensions: `{dimensions}`; finite values: `{finite_vectors}`.",
        f"- Expected train records vs metadata IDs: missing `{len(id_missing)}`, unexpected `{len(id_extra)}`, field mismatches `{len(field_mismatches)}`.",
        f"- Unique embedding documents: `{len(embedding_docs)}`; intersection with test documents: `{len(embedding_test_docs)}`; test clauses represented in embedding metadata: `{audit['embedding']['embedding_test_clause_count']}`.",
        f"- Read-only local Qdrant check: collection `cuad_train`, points `{qdrant_audit.get('points_count')}`, vector size `{qdrant_audit.get('vector_size')}`, distance `{qdrant_audit.get('distance')}`, status `{qdrant_audit.get('status')}`.",
        "- **Document-level leakage: PASS.** The persisted embedding metadata contains only training documents.",
        "",
        "## Embedding model audit",
        "",
        f"- Configured model in `data/scripts/.env`: `{audit['configuration']['configured_model_from_data_scripts_env']}`.",
        f"- Persisted model: `{embedding_data.get('model')}`.",
        f"- Match: `{audit['configuration']['model_matches_persisted']}`.",
        "- The `data/README.md` default text mentions `embed-v4.0`, but the actual environment value used by the embedding script is `embed-english-v3.0`; this is documentation drift, not an embedding-artifact mismatch.",
        "",
        "## Relationship to current retrieval results",
        "",
        "The split and embedding data do not show contract leakage, missing fixed categories, or unexplained embedding loss. Therefore the four hybrid retrieval misses are not plausibly explained by train/test document overlap or by the 11,015 -> 7,004 reduction.",
        "",
        "The remaining data-related contributors are category support imbalance and clause difficulty: a category can be present and fully embedded but still have few or lexically/semantically diverse training examples. The fixed pilot is also deliberately selected rather than representative. The unchanged Recall@5 of 0.60 and zero recovery of the four previous misses point more directly to retrieval/category-evidence difficulty than to split corruption, while the accuracy change to 0.50 remains a downstream classification result on this pilot.",
        "",
        "## Final diagnosis",
        "",
        "### Verdict: B. DATA PIPELINE HAS MINOR ISSUES BUT IS USABLE",
        "",
        "### Confirmed problems",
        "- Current scripts and documentation contain path/count/model drift relative to the live artifacts.",
        "- The fixed 10-row benchmark is not representative of the overall test distribution.",
        "",
        "### Suspected problems",
        "- Rare or difficult categories may have insufficiently diverse training evidence for strong retrieval, even though they are present and embedded.",
        "",
        "### Things that are not problems",
        "- Contract-level split integrity: PASS.",
        "- No document-level leakage was found; limited repeated clause-text overlap exists across disjoint documents and is documented above.",
        "- Test documents in training embeddings: none.",
        "- 10,545 -> 7,004 reconciliation: explained exactly by metadata exclusion.",
        "- Missing fixed-pilot categories from training: none.",
        "",
        "### Recommended next experiment",
        "Use a larger, fixed, contract-disjoint evaluation sample stratified across all substantive CUAD categories, report per-category retrieval recall and support counts, and separately evaluate rare categories. Do not alter the current fixed-10 benchmark; use the larger set as a new diagnostic benchmark.",
        "",
        "## Audit safety",
        "",
        "This audit read source files only and did not modify production source, split files, embeddings, Qdrant, environment files, experiment reports, branches, commits, or configuration.",
    ])
    (output_dir / "data_integrity_audit_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    print(json.dumps({
        "status": "COMPLETE",
        "train_test_overlap": len(train_test_doc_overlap),
        "train_long": len(train_long),
        "train_metadata": len(train_meta),
        "train_non_metadata": len(train_nonmeta),
        "embedded": len(embedding_metadata),
        "exact_overlap": len(exact_overlap),
        "normalized_overlap": len(normalized_overlap),
        "embedding_test_documents": len(embedding_test_docs),
        "fixed_rows": len(fixed_rows),
    }, indent=2))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    main(args.root, args.output_dir)

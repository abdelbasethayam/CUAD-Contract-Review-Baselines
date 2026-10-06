#!/usr/bin/env python3
"""Validate and prepare CUAD v1 for clause classification.

Design goals
------------
- Treat CUAD's 41 categories as independent annotations; do not relabel or
  delete overlapping annotations.
- Preserve the raw clause text for evidence fidelity.
- Create a conservative model-text view with only Unicode/invisible-character
  and whitespace normalization.
- Split at the CONTRACT level with the repository's existing 410/100,
  random_state=42 protocol.
- Emit machine-readable QA information so data problems are explicit.
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import re
import statistics
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from sklearn.model_selection import train_test_split


ANSWER_SUFFIX_RE = re.compile(r"\s*-\s*answer\s*$", re.IGNORECASE)
METADATA_FIELDS = {
    "Document Name",
    "Parties",
    "Agreement Date",
    "Effective Date",
    "Expiration Date",
}
EXPECTED_CONTRACTS = 510
TRAIN_CONTRACTS = 410
TEST_CONTRACTS = 100
RANDOM_STATE = 42


def find_root() -> Path:
    # data/scripts/dataset/prepare_classification.py -> repo root
    return Path(__file__).resolve().parents[3]


def parse_spans(raw: object) -> list[str]:
    if raw is None:
        return []
    text = str(raw).strip()
    if not text:
        return []
    try:
        parsed = ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return [text]
    if isinstance(parsed, list):
        return [str(item).strip() for item in parsed if str(item).strip()]
    return [str(parsed).strip()]


def clean_model_text(raw: object) -> tuple[str, list[str]]:
    original = str(raw or "")
    text = unicodedata.normalize("NFC", original)
    actions: list[str] = []
    if text != original:
        actions.append("unicode_nfc")

    text = text.replace("\u00a0", " ")
    replacements = {
        "\u00ad": "remove_soft_hyphen",
        "\u200b": "remove_zero_width_space",
        "\u200c": "remove_zero_width_non_joiner",
        "\u200d": "remove_zero_width_joiner",
        "\ufeff": "remove_bom",
    }
    for char, action in replacements.items():
        if char in text:
            text = text.replace(char, "")
            actions.append(action)

    quote_replacements = {
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
    }
    quote_changed = False
    for old, new in quote_replacements.items():
        if old in text:
            text = text.replace(old, new)
            quote_changed = True
    if quote_changed:
        actions.append("normalize_quotes")

    normalized_ws = re.sub(r"\s+", " ", text).strip()
    if normalized_ws != text:
        actions.append("normalize_whitespace")
    text = normalized_ws
    return text, sorted(set(actions))


def discover_columns(headers: list[str]) -> tuple[list[str], dict[str, str]]:
    text_columns: list[str] = []
    answer_columns: dict[str, str] = {}
    for column in headers:
        if column == "Filename":
            continue
        if ANSWER_SUFFIX_RE.search(column):
            base = ANSWER_SUFFIX_RE.sub("", column).strip()
            answer_columns[base] = column
        else:
            text_columns.append(column)
    return text_columns, answer_columns


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_long(contract_rows: list[tuple[int, dict[str, str]]], text_columns: list[str],
               answer_columns: dict[str, str]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    rows: list[dict[str, object]] = []
    parse_errors: list[dict[str, object]] = []

    for source_row, record in contract_rows:
        for clause_type in text_columns:
            raw = record.get(clause_type, "")
            if raw is None or str(raw).strip() == "":
                continue
            raw_text = str(raw).strip()
            try:
                parsed = ast.literal_eval(raw_text)
            except (ValueError, SyntaxError) as exc:
                parse_errors.append({
                    "source_row": source_row,
                    "document_id": record.get("Filename", ""),
                    "clause_type": clause_type,
                    "error": type(exc).__name__,
                    "raw_preview": raw_text[:300],
                })
                spans = [raw_text]
            else:
                if isinstance(parsed, list):
                    spans = [str(item).strip() for item in parsed if str(item).strip()]
                else:
                    spans = [str(parsed).strip()]
            for span_index, span in enumerate(spans):
                if clause_type in METADATA_FIELDS:
                    continue
                answer_column = answer_columns[clause_type]
                answer = record.get(answer_column, "")
                cleaned_text, actions = clean_model_text(span)
                rows.append({
                    "document_id": record.get("Filename", ""),
                    "clause_type": clause_type,
                    "clause_text_raw": span,
                    "clause_text_clean": cleaned_text,
                    "answer": str(answer).strip() if answer is not None else "",
                    "source_row": source_row,
                    "span_index": span_index,
                    "cleaning_actions": ";".join(actions),
                })
    return rows, parse_errors


def add_overlap_flags(rows: list[dict[str, object]]) -> None:
    groups: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        normalized = unicodedata.normalize("NFKC", str(row["clause_text_clean"])).casefold()
        groups[(str(row["document_id"]), normalized)].append(row)

    for row in rows:
        normalized = unicodedata.normalize("NFKC", str(row["clause_text_clean"])).casefold()
        group = groups[(str(row["document_id"]), normalized)]
        labels = sorted({str(item["clause_type"]) for item in group})
        row["normalized_text_hash"] = hashlib.sha1(
            normalized.encode("utf-8")
        ).hexdigest()[:16]
        row["same_text_label_count"] = len(labels)
        row["same_text_labels"] = " | ".join(labels)
        row["cross_category_span_reuse"] = len(labels) > 1


def make_report(
    raw_path: Path,
    all_rows: list[dict[str, object]],
    train_rows: list[dict[str, object]],
    test_rows: list[dict[str, object]],
    parse_errors: list[dict[str, object]],
    source_rows: list[dict[str, str]],
    text_columns: list[str],
    answer_columns: dict[str, str],
    train_docs: set[str],
    test_docs: set[str],
) -> dict[str, object]:
    texts = [str(row["clause_text_raw"]) for row in all_rows]
    lengths = [len(text) for text in texts]
    word_counts = [len(re.findall(r"\S+", text)) for text in texts]

    overlap_groups: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in all_rows:
        key = (
            str(row["document_id"]),
            hashlib.sha1(
                unicodedata.normalize("NFKC", str(row["clause_text_clean"])).casefold()
                .encode("utf-8")
            ).hexdigest(),
        )
        overlap_groups[key].append(row)
    ambiguous_groups = [
        group for group in overlap_groups.values()
        if len({str(row["clause_type"]) for row in group}) > 1
    ]
    ambiguous_rows = sum(len(group) for group in ambiguous_groups)

    # Theoretical ceiling for a forced single-label classifier when identical
    # text within one contract carries multiple CUAD labels.
    ceiling_numerator = 0
    for group in overlap_groups.values():
        ceiling_numerator += max(
            Counter(str(row["clause_type"]) for row in group).values()
        )
    ceiling = ceiling_numerator / max(len(all_rows), 1)

    yes_without_context: list[dict[str, object]] = []
    for source_row, record in enumerate(source_rows, start=2):
        for label in text_columns:
            if label in METADATA_FIELDS:
                continue
            answer = str(record.get(answer_columns[label], "") or "").strip().casefold()
            spans = parse_spans(record.get(label, ""))
            if answer == "yes" and not spans:
                yes_without_context.append({
                    "source_row": source_row,
                    "document_id": record.get("Filename", ""),
                    "clause_type": label,
                    "answer": "Yes",
                })

    train_texts = defaultdict(int)
    test_texts = defaultdict(int)
    for row in train_rows:
        train_texts[str(row["normalized_text_hash"])] += 1
    for row in test_rows:
        test_texts[str(row["normalized_text_hash"])] += 1
    common_hashes = set(train_texts) & set(test_texts)
    test_overlap_rows = sum(test_texts[key] for key in common_hashes)

    action_counts = Counter()
    for row in all_rows:
        for action in str(row.get("cleaning_actions", "")).split(";"):
            if action:
                action_counts[action] += 1

    test_counts = Counter(str(row["clause_type"]) for row in test_rows)

    return {
        "source": {
            "path": str(raw_path),
            "sha256": sha256_file(raw_path),
            "contracts": len(source_rows),
            "columns": len(source_rows[0]) if source_rows else 0,
        },
        "schema": {
            "text_columns": len(text_columns),
            "answer_columns": len(answer_columns),
            "metadata_fields": sorted(METADATA_FIELDS),
            "substantive_clause_types": len(set(str(row["clause_type"]) for row in all_rows)),
            "missing_answer_pairs": sorted(set(text_columns) - set(answer_columns)),
            "orphan_answer_pairs": sorted(set(answer_columns) - set(text_columns)),
        },
        "split": {
            "random_state": RANDOM_STATE,
            "train_contracts": len(train_docs),
            "test_contracts": len(test_docs),
            "train_substantive_rows": len(train_rows),
            "test_substantive_rows": len(test_rows),
            "train_contracts_with_substantive_labels": len({
                str(row["document_id"]) for row in train_rows
            }),
            "test_contracts_with_substantive_labels": len({
                str(row["document_id"]) for row in test_rows
            }),
        },
        "annotation_quality": {
            "parse_errors": len(parse_errors),
            "multi_label_same_contract_text_groups": len(ambiguous_groups),
            "rows_in_multi_label_groups": ambiguous_rows,
            "share_rows_in_multi_label_groups": ambiguous_rows / max(len(all_rows), 1),
            "forced_single_label_same_text_ceiling": ceiling,
            "answer_yes_without_context": len(yes_without_context),
            "answer_yes_without_context_examples": yes_without_context,
        },
        "text_quality": {
            "char_min": min(lengths) if lengths else 0,
            "char_median": statistics.median(lengths) if lengths else 0,
            "char_p95": statistics.quantiles(lengths, n=20)[18] if len(lengths) >= 20 else max(lengths, default=0),
            "char_max": max(lengths, default=0),
            "word_min": min(word_counts) if word_counts else 0,
            "word_median": statistics.median(word_counts) if word_counts else 0,
            "word_p95": statistics.quantiles(word_counts, n=20)[18] if len(word_counts) >= 20 else max(word_counts, default=0),
            "word_max": max(word_counts, default=0),
            "over_3500_chars": sum(length > 3500 for length in lengths),
            "over_256_whitespace_tokens": sum(count > 256 for count in word_counts),
            "under_or_equal_20_chars": sum(length <= 20 for length in lengths),
            "rows_with_invisible_control_formatting": sum(
                any(
                    unicodedata.category(char) in {"Cf", "Cc"}
                    and char not in "\n\t\r"
                    for char in str(row["clause_text_raw"])
                )
                for row in all_rows
            ),
            "rows_changed_by_conservative_cleaning": sum(
                bool(str(row.get("cleaning_actions", ""))) for row in all_rows
            ),
            "cleaning_action_counts": dict(action_counts),
        },
        "cross_split_text_overlap": {
            "normalized_text_hashes_in_both_splits": len(common_hashes),
            "test_rows_affected": test_overlap_rows,
            "share_test_rows": test_overlap_rows / max(len(test_rows), 1),
        },
        "test_support_lt10": {
            label: count for label, count in sorted(test_counts.items())
            if count < 10
        },
        "policy": {
            "raw_text_preserved": True,
            "conservative_normalization_only": True,
            "answers_used_as_model_input": False,
            "short_clauses_removed": False,
            "duplicate_annotations_removed": False,
            "multi_label_annotations_removed": False,
        },
    }


def main() -> int:
    root = find_root()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=root / "data" / "raw" / "cuad" / "CUAD_v1" / "master_clauses.csv",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=root / "data" / "processed" / "classification",
    )
    args = parser.parse_args()

    raw_path = args.input.resolve()
    out_dir = args.output_dir.resolve()
    if not raw_path.exists():
        raise FileNotFoundError(
            f"CUAD master_clauses.csv not found: {raw_path}"
        )

    with raw_path.open("r", encoding="utf-8-sig", newline="") as handle:
        source_rows = list(csv.DictReader(handle))
        headers = handle.fieldnames or []

    if len(source_rows) != EXPECTED_CONTRACTS:
        raise ValueError(
            f"Expected {EXPECTED_CONTRACTS} contracts; found {len(source_rows)}."
        )
    if "Filename" not in headers:
        raise ValueError("Missing Filename column.")
    if any(not str(row.get("Filename", "")).strip() for row in source_rows):
        raise ValueError("At least one contract has an empty Filename.")
    filenames = [row["Filename"] for row in source_rows]
    if len(set(filenames)) != len(filenames):
        raise ValueError("Duplicate contract filenames found.")

    text_columns, answer_columns = discover_columns(headers)
    if len(text_columns) != 41 or len(answer_columns) != 41:
        raise ValueError(
            f"Expected 41 text + 41 answer columns; found "
            f"{len(text_columns)} + {len(answer_columns)}."
        )
    missing = sorted(set(text_columns) - set(answer_columns))
    orphan = sorted(set(answer_columns) - set(text_columns))
    if missing or orphan:
        raise ValueError(f"Column pairing mismatch. missing={missing}, orphan={orphan}")

    indices = list(range(len(source_rows)))
    train_idx, test_idx = train_test_split(
        indices,
        train_size=TRAIN_CONTRACTS,
        test_size=TEST_CONTRACTS,
        random_state=RANDOM_STATE,
        shuffle=True,
    )
    train_source = [(index + 2, source_rows[index]) for index in train_idx]
    test_source = [(index + 2, source_rows[index]) for index in test_idx]
    train_docs = {row["Filename"] for _, row in train_source}
    test_docs = {row["Filename"] for _, row in test_source}
    if train_docs & test_docs:
        raise AssertionError("Contract leakage detected between train and test.")

    train_rows, train_parse_errors = build_long(train_source, text_columns, answer_columns)
    test_rows, test_parse_errors = build_long(test_source, text_columns, answer_columns)
    all_rows = train_rows + test_rows
    parse_errors = train_parse_errors + test_parse_errors
    if parse_errors:
        raise ValueError(f"Malformed span-list cells detected: {parse_errors[:3]}")

    add_overlap_flags(all_rows)
    train_len = len(train_rows)
    for index, row in enumerate(all_rows):
        row["split"] = "train" if index < train_len else "test"

    out_fields = [
        "document_id",
        "clause_type",
        "clause_text_raw",
        "clause_text_clean",
        "answer",
        "source_row",
        "span_index",
        "normalized_text_hash",
        "same_text_label_count",
        "same_text_labels",
        "cross_category_span_reuse",
        "cleaning_actions",
        "split",
    ]
    write_csv(out_dir / "cuad_classification_train_clean.csv", train_rows, out_fields)
    write_csv(out_dir / "cuad_classification_test_clean.csv", test_rows, out_fields)

    report = make_report(
        raw_path=raw_path,
        all_rows=all_rows,
        train_rows=train_rows,
        test_rows=test_rows,
        parse_errors=parse_errors,
        source_rows=source_rows,
        text_columns=text_columns,
        answer_columns=answer_columns,
        train_docs=train_docs,
        test_docs=test_docs,
    )
    (out_dir / "cuad_data_quality_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("CUAD classification preparation completed.")
    print(f"Source: {raw_path}")
    print(f"Train: {len(train_docs)} contracts / {len(train_rows)} substantive spans")
    print(f"Test:  {len(test_docs)} contracts / {len(test_rows)} substantive spans")
    print(f"Multi-label overlap rows: {report['annotation_quality']['rows_in_multi_label_groups']}")
    print(f"Conservative text changes: {report['text_quality']['rows_changed_by_conservative_cleaning']}")
    print(f"Output directory: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Optional extraction/segmentation evaluation utility.

Usage from the backend working directory::

    python -m app.core.rag.extraction_debug path/to/contract.pdf
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .segmenter import (
    LONG_CLAUSE_FALLBACK_THRESHOLD,
    _looks_like_all_caps_title,
    extract_page_layers,
    is_definition,
    split_into_clauses,
)


def _write_pages(path: Path, pages: list[str]) -> None:
    path.write_text(
        "\n\n".join(f"--- PAGE {index} ---\n{page}" for index, page in enumerate(pages, start=1)),
        encoding="utf-8",
    )


def evaluate_contract(file_path: Path, output_dir: Path) -> dict:
    layers = extract_page_layers(file_path)
    raw_pages = layers["raw_pages"]
    cleaned_pages = layers["cleaned_pages"]
    cleaned_text = "\n\n".join(cleaned_pages)
    clauses = split_into_clauses(cleaned_text)

    headings = {
        line.strip()
        for page in cleaned_pages
        for line in page.splitlines()
        if _looks_like_all_caps_title(line)
    }
    definitions = [clause for clause in clauses if is_definition(clause)]
    lengths = [len(clause) for clause in clauses]
    report = {
        "file": str(file_path),
        "pages": len(raw_pages),
        "raw_extracted_characters": sum(len(page) for page in raw_pages),
        "cleaned_characters": len(cleaned_text),
        "clauses": len(clauses),
        "definitions": len(definitions),
        "headings": len(headings),
        "min_clause_length": min(lengths) if lengths else 0,
        "average_clause_length": round(sum(lengths) / len(lengths), 1) if lengths else 0,
        "max_clause_length": max(lengths) if lengths else 0,
        "suspiciously_large_clauses": [
            index + 1 for index, length in enumerate(lengths)
            if length > LONG_CLAUSE_FALLBACK_THRESHOLD
        ],
        "suspiciously_short_clauses": [
            index + 1 for index, length in enumerate(lengths) if length < 120
        ],
        "clause_samples": [
            {"index": index + 1, "length": len(clause), "preview": clause[:200]}
            for index, clause in enumerate(clauses)
        ],
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_pages(output_dir / "extracted_pages.txt", raw_pages)
    _write_pages(output_dir / "cleaned_pages.txt", cleaned_pages)
    (output_dir / "segmented_clauses.json").write_text(
        json.dumps(
            [
                {
                    "clause_index": index + 1,
                    "length": len(clause),
                    "is_definition": is_definition(clause),
                    "text": clause,
                }
                for index, clause in enumerate(clauses)
            ],
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report_lines = [
        "# Extraction and Segmentation Report",
        "",
        f"- File: `{file_path}`",
        f"- Pages: {report['pages']}",
        f"- Raw extracted characters: {report['raw_extracted_characters']}",
        f"- Cleaned characters: {report['cleaned_characters']}",
        f"- Clauses: {report['clauses']}",
        f"- Definitions: {report['definitions']}",
        f"- Headings: {report['headings']}",
        f"- Min / average / max clause length: {report['min_clause_length']} / {report['average_clause_length']} / {report['max_clause_length']}",
        f"- Suspiciously large clause indexes: {report['suspiciously_large_clauses'] or 'none'}",
        f"- Suspiciously short clause indexes: {report['suspiciously_short_clauses'] or 'none'}",
        "",
        "## Clause previews",
        "",
    ]
    for sample in report["clause_samples"]:
        preview = sample["preview"].replace("\n", " ")
        report_lines.append(f"{sample['index']}. ({sample['length']} chars) {preview}")
    (output_dir / "segmentation_report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--output", type=Path, default=Path("reports/extraction"))
    args = parser.parse_args()
    report = evaluate_contract(args.file, args.output)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path


def flatten(nodes):
    rows = []
    for node in nodes:
        rows.append(
            {
                "clause_id": node.clause_id,
                "clause_number": node.clause_number,
                "heading": node.heading,
                "text": node.text,
                "page_start": node.page_start,
                "page_end": node.page_end,
                "parent_clause": node.parent_clause,
                "depth": node.depth,
                "source_blocks": node.source_blocks,
                "metadata": node.metadata,
            }
        )
        rows.extend(flatten(node.children))
    return rows


def main() -> None:
    root = Path(sys.argv[1])
    output = Path(sys.argv[2])
    sys.path.insert(0, str(root / "backend"))
    from app.core.rag.clause_segmenter import segment_document, validate_clause_tree

    pdf = root / "ZtoExpressCaymanInc_20160930_F-1_EX-10.10_9752871_EX-10.10_Transportation Agreement.pdf"
    nodes = segment_document(pdf)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "source": str(pdf),
                "parser_requested": "docling",
                "top_level_count": len(nodes),
                "total_node_count": len(flatten(nodes)),
                "validation_issues": validate_clause_tree(nodes),
                "nodes": flatten(nodes),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"top_level_count": len(nodes), "total_node_count": len(flatten(nodes))}))


if __name__ == "__main__":
    main()

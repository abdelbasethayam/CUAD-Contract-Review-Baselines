# Additional improvements (round 2)

## Added

1. **Label-diverse retrieval** (`retriever.py` + `candidate_utils.py`)
   - Over-fetch Top-K × 3, keep max 2 hits per `clause_type`.
   - Reduces candidate collapse when the neighborhood is one label.

2. **Expanded high-precision rules** (`high_precision_rules.py`)
   - Broader coverage: MFN, Exclusivity, Change Of Control, Renewal, License Grant, Warranty Duration, Minimum Commitment, No-Solicit (employees/customers), tighter Insurance/Termination patterns.

3. **Confidence fusion** (`candidate_utils.fuse_confidence`)
   - Combines retrieval score + model validity + rule agreement for UI/logging.

4. **Embed-side preprocess helper** (`embed_preprocess.py`)
   - Use `text_for_embedding()` / `texts_for_embedding()` before Cohere so queries match cleaned train text.

5. **Unit tests** (`backend/tests/test_high_precision_rules.py`)
   - Rules, preprocess, diversify, confidence.

## Wire in call sites

```python
from backend.app.core.rag.embed_preprocess import text_for_embedding
from backend.app.core.rag.high_precision_rules import high_precision_rule_label
from backend.app.core.rag.candidate_utils import fuse_confidence

query = text_for_embedding(raw_clause)
# embed(query) -> retrieve_similar(..., diversify=True)
```

Generator already uses rules internally; prefer importing `high_precision_rules` module going forward so rules stay in one place.

## Run tests

```bash
pip install pytest
pytest backend/tests/test_high_precision_rules.py -q
```

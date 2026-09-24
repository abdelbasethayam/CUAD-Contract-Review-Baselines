# ZTO Ollama-vs-Retrieval Diagnostic

Status: **COMPLETE**

## 1. Environment

- Parser: `docling`
- Python: `3.12.14`
- Parsed blocks: `46`
- Top-level clauses: `16`
- Selected clauses: `12`
- Embedding model: `embed-english-v3.0`
- Qdrant collection: `cuad_train`
- Qdrant path: `/workspace/diagnostics/zto_retrieval_test/qdrant_snapshot` (isolated read-only snapshot)
- Retrieval Top-K: `5`
- Ollama endpoint: `http://host.docker.internal:11434`
- Ollama model: `llama3.2:3b`
- Generation options: `{"temperature": 0, "num_gpu": 0, "use_mmap": true, "num_ctx": 4096}`
- Runtime packages: `{"torch": "2.14.0+cpu", "transformers": "5.17.0", "accelerate": "1.15.0", "docling": "2.126.0", "docling-ibm-models": "4.0.2", "opencv-python-headless": "4.14.0.94"}`
- Timestamp: `2026-09-10T10:18:54.657463+00:00`

## 2. Pipeline Reproduction

The diagnostic imports the existing `segment_document`, `embed_queries`, `retrieve_similar`, `extract_legal_information`, `build_prompt`, `call_ollama`, `parse_prediction`, and `classify_clause` implementations. It does not modify them. The Qdrant client reads an isolated snapshot because the live local store is locked by the running application containers.

## 3. Per-Clause Results

| Clause | Ground Truth | Qdrant Top-1 | Qdrant Score | Ollama Prediction | Prediction in Top-K? | Decision Relationship |
|---|---|---|---:|---|---|---|
| 1. | None | Rofr/Rofo/Rofn | 0.5638601034595816 | License Grant | Yes | OLLAMA_SELECTED_RETRIEVED_LABEL |
| 3. | None | Revenue/Profit Sharing | 0.5123864974618589 | License Grant | No | OLLAMA_SELECTED_LABEL_NOT_RETRIEVED |
| 4. | None | Notice Period To Terminate Renewal | 0.4799134427119086 | Renewal Term | Yes | OLLAMA_SELECTED_RETRIEVED_LABEL |
| 5. | None | Exclusivity | 0.5255886423226489 | Exclusivity | Yes | RETRIEVAL_TOP1_MATCH |
| 6. | Insurance | Insurance | 0.7654467867011041 | Insurance | Yes | RETRIEVAL_TOP1_MATCH |
| 9. | None | Liquidated Damages | 0.6474151265481198 | Termination For Convenience | Yes | OLLAMA_SELECTED_RETRIEVED_LABEL |
| 11. | None | Termination For Convenience | 0.6030398783129638 | Anti-Assignment | Yes | OLLAMA_SELECTED_RETRIEVED_LABEL |
| 12. | None | Governing Law | 0.531984645929346 | Governing Law | Yes | RETRIEVAL_TOP1_MATCH |
| 13. | None | Covenant Not To Sue | 0.5066150163222621 | Anti-Assignment | Yes | OLLAMA_SELECTED_RETRIEVED_LABEL |
| 14. | None | Anti-Assignment | 0.4949521647860077 | Anti-Assignment | Yes | RETRIEVAL_TOP1_MATCH |
| 5(e) | Liquidated Damages | Liquidated Damages | 0.8183981719704212 | Liquidated Damages | Yes | RETRIEVAL_TOP1_MATCH |
| 10. | Liquidated Damages | Liquidated Damages | 0.707168526626664 | Liquidated Damages | Yes | RETRIEVAL_TOP1_MATCH |

## 4. Detailed Top-K

### 1.

Query (114 characters): 1. Party B shall provide parcel transportation services on highway line-haul routes based on the needs of Party A.

1. `Rofr/Rofo/Rofn` — `0.563860` — `None` — selected: no
2. `Insurance` — `0.556269` — `None` — selected: no
3. `Most Favored Nation` — `0.538966` — `None` — selected: no
4. `Most Favored Nation` — `0.530388` — `None` — selected: no
5. `License Grant` — `0.528890` — `None` — selected: yes

Ollama parsed prediction: `License Grant`
Raw response: `{"clause_type": "License Grant"}`

### 3.

Query (30 characters): 3. Freight and payment method:

1. `Revenue/Profit Sharing` — `0.512386` — `None` — selected: no
2. `Liquidated Damages` — `0.456247` — `None` — selected: no
3. `Minimum Commitment` — `0.454588` — `None` — selected: no
4. `Revenue/Profit Sharing` — `0.450556` — `None` — selected: no
5. `Minimum Commitment` — `0.447248` — `None` — selected: no

Ollama parsed prediction: `License Grant`
Raw response: `{"clause_type": "License Grant"}`

### 4.

Query (48 characters): 4. Transportation route, time and relevant rules

1. `Notice Period To Terminate Renewal` — `0.479913` — `None` — selected: no
2. `Renewal Term` — `0.479913` — `None` — selected: yes
3. `Minimum Commitment` — `0.435367` — `None` — selected: no
4. `Minimum Commitment` — `0.411138` — `None` — selected: no
5. `Liquidated Damages` — `0.409045` — `None` — selected: no

Ollama parsed prediction: `Renewal Term`
Raw response: `{"clause_type": "Renewal Term"}`

### 5.

Query (122 characters): 5. In order to guarantee rapid transfer of Party A's parcel, Party B shall strictly comply with the following obligations:

1. `Exclusivity` — `0.525589` — `None` — selected: yes
2. `Rofr/Rofo/Rofn` — `0.523626` — `None` — selected: no
3. `Audit Rights` — `0.522535` — `None` — selected: no
4. `Insurance` — `0.509253` — `None` — selected: no
5. `Most Favored Nation` — `0.507602` — `None` — selected: no

Ollama parsed prediction: `Exclusivity`
Raw response: `{"clause_type": "Exclusivity"}`

### 6.

Query (455 characters): 6. Party B shall purchase sufficient insurance for the transportation vehicles. The coverage of third-party liability insurance shall not be lower than RMB1 million. In addition to vehicle personnel insurance, Party B shall at least purchase injury insurance for two persons with…

1. `Insurance` — `0.765447` — `None` — selected: yes
2. `Insurance` — `0.648227` — `None` — selected: yes
3. `Insurance` — `0.640020` — `None` — selected: yes
4. `Insurance` — `0.576255` — `None` — selected: yes
5. `Liquidated Damages` — `0.557952` — `None` — selected: no

Ollama parsed prediction: `Insurance`
Raw response: `{"clause_type": "Insurance"}`

### 9.

Query (236 characters): 9. Party A has the right to terminate this Agreement if Party B has breached the above articles in this Agreement. The termination of this Agreement shall not prejudice Party A's right to hold Party B responsible for breach of contract.

1. `Liquidated Damages` — `0.647415` — `None` — selected: no
2. `Termination For Convenience` — `0.638911` — `None` — selected: yes
3. `Cap On Liability` — `0.614421` — `None` — selected: no
4. `Termination For Convenience` — `0.610418` — `None` — selected: yes
5. `Cap On Liability` — `0.606534` — `None` — selected: no

Ollama parsed prediction: `Termination For Convenience`
Raw response: `{"clause_type": "Termination For Convenience"}`

### 11.

Query (195 characters): 11. Without Party A's approval, Party B shall not transfer the carriage of goods to any third party in the designated route. Otherwise, Party A has the right to terminate this Agreement directly.

1. `Termination For Convenience` — `0.603040` — `None` — selected: no
2. `Anti-Assignment` — `0.588578` — `None` — selected: yes
3. `Termination For Convenience` — `0.580334` — `None` — selected: no
4. `Anti-Assignment` — `0.578725` — `None` — selected: yes
5. `Anti-Assignment` — `0.576215` — `None` — selected: yes

Ollama parsed prediction: `Anti-Assignment`
Raw response: `{"clause_type": "Anti-Assignment"}`

### 12.

Query (210 characters): 12. Any dispute arising out of the execution of this Agreement, which cannot be negotiated and settled by both Parties, shall be subject to the jurisdiction of the People's Court where this Agreement is signed.

1. `Governing Law` — `0.531985` — `None` — selected: yes
2. `Governing Law` — `0.526947` — `None` — selected: yes
3. `Governing Law` — `0.526936` — `None` — selected: yes
4. `Governing Law` — `0.522073` — `None` — selected: yes
5. `Anti-Assignment` — `0.520462` — `None` — selected: no

Ollama parsed prediction: `Governing Law`
Raw response: `{"clause_type": "Governing Law"}`

### 13.

Query (175 characters): 13. The annex of this Agreement constitutes a part of this Agreement and has the same effect as this Agreement. Any undealt matter can be negotiated and added by both Parties.

1. `Covenant Not To Sue` — `0.506615` — `None` — selected: no
2. `Anti-Assignment` — `0.499909` — `None` — selected: yes
3. `Anti-Assignment` — `0.499247` — `None` — selected: yes
4. `Anti-Assignment` — `0.496444` — `None` — selected: yes
5. `Anti-Assignment` — `0.496370` — `None` — selected: yes

Ollama parsed prediction: `Anti-Assignment`
Raw response: `{"clause_type": "Anti-Assignment"}`

### 14.

Query (155 characters): 14. This Agreement takes effect upon the signatures and seals of both Parties in triplicate. Party A shall have two copies and Party B shall have one copy.

1. `Anti-Assignment` — `0.494952` — `None` — selected: yes
2. `Anti-Assignment` — `0.484107` — `None` — selected: yes
3. `Anti-Assignment` — `0.477143` — `None` — selected: yes
4. `Anti-Assignment` — `0.475842` — `None` — selected: yes
5. `Joint Ip Ownership` — `0.473987` — `None` — selected: no

Ollama parsed prediction: `Anti-Assignment`
Raw response: `{"clause_type": "Anti-Assignment"}`

### 5(e)

Query (870 characters): (e) Party B shall arrive at the network partners determined by Party A according to the time and route stipulated in this Agreement, and strictly comply with the start time and end time. Unless otherwise approved by Party A, in the event of parcel transfer due to Party B's vehic…

1. `Liquidated Damages` — `0.818398` — `None` — selected: yes
2. `Liquidated Damages` — `0.603121` — `None` — selected: yes
3. `Liquidated Damages` — `0.588036` — `None` — selected: yes
4. `Liquidated Damages` — `0.569735` — `None` — selected: yes
5. `Liquidated Damages` — `0.561765` — `None` — selected: yes

Ollama parsed prediction: `Liquidated Damages`
Raw response: `{"clause_type": "Liquidated Damages"}`

### 10.

Query (385 characters): 10. Party B shall obtain Party A's written consent in the case the early termination of the Agreement. Party B shall pay one-month freight as liquidated damages in case of termination of the Agreement without consent. Within the contract period, Party B shall not charge the frei…

1. `Liquidated Damages` — `0.707169` — `None` — selected: yes
2. `Liquidated Damages` — `0.592169` — `None` — selected: yes
3. `Liquidated Damages` — `0.579604` — `None` — selected: yes
4. `Termination For Convenience` — `0.567426` — `None` — selected: no
5. `Liquidated Damages` — `0.554277` — `None` — selected: yes

Ollama parsed prediction: `Liquidated Damages`
Raw response: `{"clause_type": "Liquidated Damages"}`

## 5. Ground-Truth Analysis

- Clauses with CUAD ground truth: `3`
- Clauses without CUAD ground truth: `9`
- Retrieval Top-1 correctness on ground-truth clauses: `1.0`
- Retrieval Top-5 availability on ground-truth clauses: `1.0`
- Ollama final-label correctness on ground-truth clauses: `1.0`

## 6. Ollama Behavior

- Selected Qdrant Top-1: `6`
- Selected another retrieved label: `5`
- Selected a label absent from Top-K: `1`
- UNKNOWN results: `0`
- Classifier errors: `0`

## 7. Key Findings

The per-clause relationship fields distinguish retrieval evidence from the Ollama decision. Clauses without CUAD annotations are not treated as classification errors.

## 8. Final Conclusion

1. Docling segmentation succeeded: **Yes** — `docling`, `46` parsed blocks, `16` top-level clauses, and no segmentation validation issues.
2. Qdrant retrieval executed: **Yes** — `12/12` clauses completed Top-5 retrieval against the isolated `cuad_train` snapshot.
3. Ollama generation executed: **Yes** — `12/12` clauses parsed successfully with no classifier errors.
4. Ollama selected Qdrant Top-1: `6/12` clauses (50.0%).
5. Ollama selected another label present in Top-5: `5/12` clauses (41.7%).
6. Ollama selected a label absent from Top-5: `1/12` clauses (8.3%), clause `3.`.
7. On the `3` clauses with CUAD ground truth, retrieval contained the correct label in Top-5: `3/3`; Top-1: `3/3`. Ollama final-label correctness was also `3/3`.
8. No ground-truth final-label error occurred. Unannotated clauses are reported diagnostically but are not called correct or incorrect.

## 9. Decision

This is a leakage-affected diagnostic because the ZTO document is present in the training collection. No classifier or retrieval fix is implemented by this experiment.

## Safety Check

- Only diagnostic files under `diagnostics/zto_retrieval_test/` were changed.
- No production source, `.env`, prompt, segmentation code, Qdrant point, collection, embedding, or model configuration was changed.
- No Git commit was created.

AI Contract Review

This project classifies commercial contract clauses with the CUAD pipeline and
adds a separate Legal Knowledge RAG layer for potential review indicators.

Current MVP supported risk categories:

1. Limitation of Liability
2. Indemnification
3. Termination
4. Intellectual Property

CUAD is used for clause classification only. It is not used as a risk-label
dataset. The risk layer combines the uploaded clause, CUAD clause type,
retrieved legal guidance, documented risk indicators, and local Ollama
reasoning to identify "Potential Risk Indicators".

The output is review support, not legal advice, a legal judgment, or a finding
that a clause is illegal.
"# CUAD-Contract-Review-Baselines" 

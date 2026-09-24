FROM ai-contract-review:latest

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OLLAMA_URL=http://host.docker.internal:11434 \
    OLLAMA_BASE_URL=http://host.docker.internal:11434

COPY diagnostics/zto_retrieval_test/ollama_classifier_test/diagnostic_torch_requirements.txt /tmp/diagnostic_torch_requirements.txt
COPY diagnostics/zto_retrieval_test/ollama_classifier_test/diagnostic_requirements.txt /tmp/diagnostic_requirements.txt
RUN pip install --no-cache-dir \
        --index-url https://download.pytorch.org/whl/cpu \
        -r /tmp/diagnostic_torch_requirements.txt && \
    pip install --no-cache-dir -r /tmp/diagnostic_requirements.txt

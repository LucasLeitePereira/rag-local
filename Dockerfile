FROM python:3.11-slim

ARG COM_EMBEDDINGS=true

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src
COPY avaliacao ./avaliacao

RUN if [ "$COM_EMBEDDINGS" = "true" ]; then \
        pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu ".[embeddings]"; \
    else \
        pip install --no-cache-dir .; \
    fi

# Baixa o modelo de embeddings durante o build, não no primeiro uso — importante
# para o container não precisar de rede na primeira execução (ex.: demonstração).
RUN if [ "$COM_EMBEDDINGS" = "true" ]; then \
        python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-small')"; \
    fi

ENV HF_HUB_OFFLINE=1

RUN useradd --create-home --uid 1000 docserver \
    && mkdir -p /app/docs-fonte /app/docs-normalizado /app/data \
    && chown -R docserver:docserver /app
USER docserver

VOLUME ["/app/docs-fonte", "/app/docs-normalizado", "/app/data"]

CMD ["docserver", "serve"]

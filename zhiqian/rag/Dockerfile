# syntax=docker/dockerfile:1.7
FROM python:3.11-slim
WORKDIR /app

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/data/.hf_cache \
    TRANSFORMERS_OFFLINE=0

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential curl && \
    rm -rf /var/lib/apt/lists/*

# v2-step-04：BUILD_ML=1 时走 requirements-ml.txt（含 torch + FlagEmbedding，镜像~2GB）。
# 默认 0 时仅装轻依赖，走 hash 向量退化路径。
ARG BUILD_ML=0
ENV BUILD_ML=${BUILD_ML}

COPY requirements.txt requirements-ml.txt ./
RUN if [ "$BUILD_ML" = "1" ]; then \
        echo "[Dockerfile] BUILD_ML=1: installing heavy ML deps" && \
        pip install -r requirements-ml.txt ; \
    else \
        echo "[Dockerfile] BUILD_ML=0: installing light deps only" && \
        pip install -r requirements.txt ; \
    fi

COPY . .
RUN pip install -e .

EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]

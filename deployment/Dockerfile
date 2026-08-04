# Human-readable tags are intentional until this image passes a real GPU build/run.
# Do not claim digest pinning before that qualification.
FROM node:24-bookworm-slim AS frontend-build

WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm test -- --run
RUN npm run build

# CUDA 12.8 matches the exact PyTorch cu128 wheel installed below. Ubuntu 24.04
# provides the required CPython 3.12 runtime. Digest pinning remains pending.
FROM nvidia/cuda:12.8.1-runtime-ubuntu24.04 AS runtime

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        ca-certificates \
        python3.12 \
        python3.12-venv \
    && rm -rf /var/lib/apt/lists/*

COPY backend/ /tmp/backend/
RUN python3.12 -m venv "$VIRTUAL_ENV" \
    && python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir \
        --extra-index-url https://download.pytorch.org/whl/cu128 \
        torch==2.7.1+cu128 \
        nvmolkit==0.5.0 \
        /tmp/backend \
    && rm -rf /tmp/backend

WORKDIR /app/backend
COPY backend/app/ ./app/
COPY data/ /app/data/
COPY --from=frontend-build /build/frontend/dist/ /app/frontend/dist/

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home app \
    && chown -R app:app /app

USER app
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

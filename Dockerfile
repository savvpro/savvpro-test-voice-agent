FROM node:24-alpine AS frontend
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM ghcr.io/astral-sh/uv:0.12.3 AS uv
FROM python:3.12-slim
COPY --from=uv /uv /uvx /bin/
WORKDIR /app
ENV PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY backend/ ./backend/
COPY --from=frontend /web/dist ./frontend/dist/
RUN useradd --create-home bayline && chown -R bayline:bayline /app
USER bayline
EXPOSE 8000
# Hosted ingress terminates TLS; trust its forwarded scheme for same-origin checks.
CMD ["sh", "-c", "exec .venv/bin/uvicorn backend.app:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --proxy-headers --forwarded-allow-ips '*'"]

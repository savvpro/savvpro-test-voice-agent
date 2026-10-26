FROM node:24-bookworm-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json frontend/.npmrc ./
RUN npm ci --ignore-scripts
COPY frontend/ ./
RUN npm run build

FROM python:3.14-slim AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    DATABASE_URL=sqlite:////data/riverside.db \
    STATIC_DIRECTORY=/app/web \
    ALLOWED_ORIGINS=http://127.0.0.1:8080,http://localhost:8080
WORKDIR /app/backend
COPY backend/requirements.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock
COPY backend/pyproject.toml ./
COPY backend/src/ ./src/
RUN pip install --no-cache-dir --no-deps . \
    && useradd --uid 10001 --create-home app \
    && mkdir -p /data && chown app:app /data
COPY --from=web /web/dist/ /app/web/
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=3)"
CMD ["python", "-m", "lost_property.bootstrap"]

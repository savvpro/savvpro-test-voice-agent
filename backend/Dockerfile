FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 DATABASE_PATH=/data/clinic.db
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN useradd -r -u 10001 app && mkdir /data && chown app /data
USER app
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=3s --start-period=5s --retries=10 \
  CMD python -c "import urllib.request as u; u.urlopen('http://localhost:8000/api/health', timeout=2)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

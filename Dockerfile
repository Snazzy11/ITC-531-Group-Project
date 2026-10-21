FROM python:3.14.7-slim-trixie

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/app

WORKDIR /app

COPY requirements.txt .
RUN apt-get update \
    && apt-get install -y --no-install-recommends file \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements.txt

COPY ./app/ /app/

RUN groupadd --gid 10001 seekr \
    && useradd --uid 10001 --gid seekr --create-home seekr \
    && mkdir -p /app/logs \
    && chown seekr:seekr /app/logs

USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=12s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=10).close()"]

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--root-path", "/api/v1"]

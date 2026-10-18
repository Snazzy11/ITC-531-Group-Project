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

## ALTERNATE STRATEGY of exporting from UV in dockerfile so we dont have to maintain two
#FROM python:3.12-slim-bookworm
#
#COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
#
#ENV PYTHONUNBUFFERED=1
#ENV UV_LINK_MODE=copy
#
#WORKDIR /app
#
## Native dependencies for pillow and pillow-heif
#RUN apt-get update \
#    && apt-get install -y --no-install-recommends \
#        file \
#        libheif-dev \
#        libjpeg-dev \
#        zlib1g-dev \
#        pkg-config \
#    && rm -rf /var/lib/apt/lists/*
#
## Install locked Python dependencies without the local project
#COPY pyproject.toml uv.lock ./
#
#RUN uv export --frozen --no-dev --no-emit-project \
#        --format requirements-txt \
#        --output-file /tmp/requirements.txt \
#    && uv pip install --system -r /tmp/requirements.txt \
#    && rm /tmp/requirements.txt
#
#ENV PYTHONPATH=/app/app
#
#COPY ./app/ /app/
#
#EXPOSE 8000
#
#CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--root-path", "/api/v1"]

FROM python:3.13-slim AS builder
WORKDIR /build
RUN pip install --no-cache-dir uv==0.13.1
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN uv export --frozen --no-dev --extra postgresql --no-emit-project -o requirements.txt
RUN uv build --wheel && python -m venv /opt/venv && uv pip install --python /opt/venv/bin/python --no-cache -r requirements.txt dist/*.whl

FROM python:3.13-slim
ENV PATH="/opt/venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN groupadd --gid 10001 forge && useradd --uid 10001 --gid forge --create-home forge && mkdir /app && chown forge:forge /app
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
USER forge
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=3)"]
CMD ["uvicorn", "modular_forge.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers", "--no-server-header"]

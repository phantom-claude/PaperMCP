# Multi-stage build for smaller image
FROM python:3.12-slim AS builder

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src/ src/

RUN pip install --no-cache-dir build \
    && python -m build --wheel \
    && pip install --no-cache-dir dist/*.whl

FROM python:3.12-slim

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/paper-mcp /usr/local/bin/paper-mcp
COPY --from=builder /usr/local/bin/paper-search /usr/local/bin/paper-search

# Environment variables (override at runtime with -e)
ENV PAPER_MCP_STORAGE=""
ENV PAPER_SEARCH_MCP_UNPAYWALL_EMAIL=""
ENV PAPER_SEARCH_MCP_CORE_API_KEY=""
ENV PAPER_SEARCH_MCP_SEMANTIC_SCHOLAR_API_KEY=""
ENV PAPER_SEARCH_MCP_ZENODO_ACCESS_TOKEN=""
ENV PAPER_SEARCH_MCP_DOAJ_API_KEY=""
ENV PAPER_SEARCH_MCP_GOOGLE_SCHOLAR_PROXY_URL=""
ENV PAPER_SEARCH_MCP_IEEE_API_KEY=""
ENV PAPER_SEARCH_MCP_ACM_API_KEY=""

CMD ["paper-mcp"]

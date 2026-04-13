"""
Smoke tests for all MCP paper sources.

Each test verifies that a source module can be imported and its main
functions execute without crashing.  We use a simple "deep learning"
query so that every source is expected to return *something*.

These are integration tests that hit real APIs, so they are allowed
to be slow and may occasionally fail due to rate-limiting or network
issues.
"""

import importlib
import pytest

# ── helpers ──────────────────────────────────────────────────────────

QUERY = "deep learning"
MAX_RESULTS = 2

# Functional async source modules (original PaperMCP)
ASYNC_SOURCE_MODULES = [
    "paper_mcp.sources.arxiv",
    "paper_mcp.sources.dblp",
    "paper_mcp.sources.scholar",
    "paper_mcp.sources.paperswithcode",
    "paper_mcp.sources.huggingface",
    "paper_mcp.sources.semanticscholar",
    "paper_mcp.sources.crossref",
    "paper_mcp.sources.openalex",
    "paper_mcp.sources.pubmed",
    "paper_mcp.sources.biorxiv",
    "paper_mcp.sources.europepmc",
    "paper_mcp.sources.hal",
    "paper_mcp.sources.pmc",
    "paper_mcp.sources.doaj",
    "paper_mcp.sources.zenodo",
    "paper_mcp.sources.openaire",
    "paper_mcp.sources.inspirehep",
    "paper_mcp.sources.unpaywall",
    "paper_mcp.sources.chemrxiv",
]

# Class-based source modules
CLASS_SOURCE_MODULES = [
    "paper_mcp.sources.google_scholar",
    "paper_mcp.sources.iacr",
    "paper_mcp.sources.core",
    "paper_mcp.sources.citeseerx",
    "paper_mcp.sources.ssrn",
    "paper_mcp.sources.base_search",
    "paper_mcp.sources.medrxiv",
    "paper_mcp.sources.sci_hub",
]

ALL_SOURCE_MODULES = ASYNC_SOURCE_MODULES + CLASS_SOURCE_MODULES

# Infrastructure modules
INFRA_MODULES = [
    "paper_mcp.paper",
    "paper_mcp.config",
    "paper_mcp.utils",
    "paper_mcp.sources.base",
    "paper_mcp.sources.oaipmh",
]


# ── import tests ─────────────────────────────────────────────────────

@pytest.mark.parametrize("module_path", ALL_SOURCE_MODULES + INFRA_MODULES)
def test_source_importable(module_path: str):
    """Every source module should import without errors."""
    mod = importlib.import_module(module_path)
    assert mod is not None


# ── search / main-function tests ─────────────────────────────────────

async def _call_search(module_path: str):
    """Call the primary search/list function of a source module."""
    mod = importlib.import_module(module_path)
    name = module_path.rsplit(".", 1)[-1]

    if name == "arxiv":
        return await mod.search_papers(QUERY, MAX_RESULTS)
    elif name == "huggingface":
        return await mod.get_daily_papers()
    elif name == "paperswithcode":
        return await mod.search_papers(title=QUERY)
    elif name == "chemrxiv":
        return await mod.search(QUERY, MAX_RESULTS)
    elif name in (
        "dblp", "scholar", "semanticscholar", "crossref",
        "openalex", "pubmed", "biorxiv", "europepmc",
        "hal", "pmc", "doaj", "zenodo", "openaire", "inspirehep",
    ):
        return await mod.search(QUERY, MAX_RESULTS)
    else:
        pytest.skip(f"No known search entry-point for {name}")


@pytest.mark.parametrize("module_path", ASYNC_SOURCE_MODULES)
async def test_source_search(module_path: str):
    """Each async source's search function should return a non-empty string."""
    result = await _call_search(module_path)
    assert isinstance(result, str)
    assert len(result) > 0


# ── unified search test ──────────────────────────────────────────────

async def test_unified_search():
    """The unified search tool should aggregate results."""
    from paper_mcp.sources import unified

    result = await unified.search(QUERY, None, MAX_RESULTS)
    assert isinstance(result, str)
    assert "Unified Search" in result or "No results" in result

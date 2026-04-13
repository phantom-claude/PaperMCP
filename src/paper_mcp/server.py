"""
PaperMCP — All-in-one academic paper MCP server.

Unified MCP server combining 30+ academic paper sources into 4 clean tools:
ArXiv, HuggingFace Daily Papers, Google Scholar, OpenReview, DBLP,
PapersWithCode, Semantic Scholar, CrossRef, OpenAlex, PubMed, bioRxiv/medRxiv,
Europe PMC, HAL, PMC, DOAJ, Zenodo, OpenAIRE, INSPIRE-HEP, IACR, CORE,
CiteSeerX, SSRN, BASE, ChemRxiv, Sci-Hub, and more.
"""

import logging
from typing import Optional

from mcp.server.fastmcp import FastMCP

from .sources import unified

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("paper_mcp")

mcp = FastMCP("paper-mcp")

# ─── Unified Tools (cross-source) ────────────────────────────────────


@mcp.tool()
async def search(
    query: str,
    sources: Optional[str] = None,
    max_results: int = 5,
) -> str:
    """Search for papers across ALL sources in parallel.

    sources: comma-separated list — defaults to all 25+ sources.
    Includes: arxiv, dblp, scholar, pwc, hf, ss, crossref, openalex, pubmed,
    biorxiv, europepmc, hal, pmc, doaj, zenodo, openaire, inspirehep,
    google_scholar, iacr, core, citeseerx, ssrn, base, medrxiv, chemrxiv.
    Returns merged results from every selected source."""
    return await unified.search(query, sources, max_results)


@mcp.tool()
async def download(paper_id: str) -> str:
    """Download a paper by ID or URL. Auto-detects source.

    Supports: ArXiv IDs (2401.12345), DOIs (10.xxxx/...), ArXiv/OpenReview URLs, or any PDF URL."""
    return await unified.download(paper_id)


@mcp.tool()
async def read(paper_id: str) -> str:
    """Read a paper's full text or metadata. Auto-detects source from ID/URL.

    Supports: ArXiv IDs (download first), DOIs, Semantic Scholar IDs, or direct PDF/HTML URLs."""
    return await unified.read(paper_id)


@mcp.tool()
async def list_papers(source: Optional[str] = None) -> str:
    """List available papers — locally downloaded ArXiv PDFs and today's HuggingFace trending papers.

    Filter by source: arxiv, hf."""
    return await unified.list_papers(source)


# ─── Server Entry Point ──────────────────────────────────────────────

def main():
    """Run the PaperMCP server."""
    mcp.run()


if __name__ == "__main__":
    main()

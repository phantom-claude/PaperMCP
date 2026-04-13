"""Semantic Scholar source — search papers, citations, and references."""

import logging
import asyncio
from typing import Optional

import httpx

logger = logging.getLogger("paper_mcp.semanticscholar")

BASE_URL = "https://api.semanticscholar.org/graph/v1"
HEADERS = {"User-Agent": "paper-mcp/0.1.0"}
FIELDS = "paperId,title,authors,year,abstract,citationCount,url,externalIds,venue"


async def search(query: str, max_results: int = 10) -> str:
    """Search Semantic Scholar for papers by keywords."""
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        try:
            resp = await client.get(
                f"{BASE_URL}/paper/search",
                params={"query": query, "limit": min(max_results, 100), "fields": FIELDS},
                headers=HEADERS,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            return f"Semantic Scholar error: {e}"

    papers = data.get("data", [])
    if not papers:
        return f"No Semantic Scholar results for '{query}'."

    lines = [f"Semantic Scholar results for '{query}' — {len(papers)} papers:\n"]
    for p in papers:
        authors = [a.get("name", "") for a in (p.get("authors") or [])]
        lines.append(f"**{p.get('title', 'Untitled')}**")
        if authors:
            lines.append(f"  Authors: {', '.join(authors[:5])}")
        lines.append(f"  Year: {p.get('year', 'N/A')} | Citations: {p.get('citationCount', 0)}")
        if p.get("venue"):
            lines.append(f"  Venue: {p['venue']}")
        if p.get("abstract"):
            lines.append(f"  Abstract: {p['abstract'][:200]}...")
        ext = p.get("externalIds") or {}
        if ext.get("ArXiv"):
            lines.append(f"  ArXiv: {ext['ArXiv']}")
        if ext.get("DOI"):
            lines.append(f"  DOI: {ext['DOI']}")
        lines.append(f"  URL: {p.get('url', '')}")
        lines.append("")

    return "\n".join(lines)


async def get_paper(paper_id: str) -> str:
    """Get paper details from Semantic Scholar by S2 paper ID, ArXiv ID, DOI, etc."""
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        try:
            resp = await client.get(
                f"{BASE_URL}/paper/{paper_id}",
                params={"fields": FIELDS + ",references.title,citations.title"},
                headers=HEADERS,
            )
            resp.raise_for_status()
            p = resp.json()
        except Exception as e:
            return f"Semantic Scholar error: {e}"

    authors = [a.get("name", "") for a in (p.get("authors") or [])]
    lines = [f"**{p.get('title', 'Untitled')}**"]
    if authors:
        lines.append(f"  Authors: {', '.join(authors)}")
    lines.append(f"  Year: {p.get('year', 'N/A')} | Citations: {p.get('citationCount', 0)}")
    if p.get("venue"):
        lines.append(f"  Venue: {p['venue']}")
    if p.get("abstract"):
        lines.append(f"  Abstract: {p['abstract']}")
    ext = p.get("externalIds") or {}
    if ext.get("ArXiv"):
        lines.append(f"  ArXiv: {ext['ArXiv']}")
    if ext.get("DOI"):
        lines.append(f"  DOI: {ext['DOI']}")
    lines.append(f"  URL: {p.get('url', '')}")

    refs = p.get("references") or []
    if refs:
        lines.append(f"\n  Top References ({min(len(refs), 5)}):")
        for r in refs[:5]:
            if r and r.get("title"):
                lines.append(f"    - {r['title']}")

    cites = p.get("citations") or []
    if cites:
        lines.append(f"\n  Recent Citations ({min(len(cites), 5)}):")
        for c in cites[:5]:
            if c and c.get("title"):
                lines.append(f"    - {c['title']}")

    return "\n".join(lines)

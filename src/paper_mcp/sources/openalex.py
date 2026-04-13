"""OpenAlex source — open catalog of the global research system."""

import logging
from typing import Optional

import httpx

logger = logging.getLogger("paper_mcp.openalex")

BASE_URL = "https://api.openalex.org"
HEADERS = {
    "User-Agent": "paper-mcp/0.1.0 (https://github.com/ScienceAIHub/PaperMCP)",
}


async def search(query: str, max_results: int = 10) -> str:
    """Search OpenAlex for scholarly works by keywords."""
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        try:
            resp = await client.get(
                f"{BASE_URL}/works",
                params={
                    "search": query,
                    "per_page": min(max_results, 200),
                    "sort": "relevance_score:desc",
                },
                headers=HEADERS,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            return f"OpenAlex error: {e}"

    results = data.get("results", [])
    if not results:
        return f"No OpenAlex results for '{query}'."

    lines = [f"OpenAlex results for '{query}' — {len(results)} works:\n"]
    for item in results:
        title = item.get("title", "Untitled") or "Untitled"
        authors = []
        for a in (item.get("authorships") or []):
            name = (a.get("author") or {}).get("display_name", "")
            if name:
                authors.append(name)

        lines.append(f"**{title}**")
        if authors:
            lines.append(f"  Authors: {', '.join(authors[:5])}")
        lines.append(f"  Year: {item.get('publication_year', 'N/A')} | Citations: {item.get('cited_by_count', 0)}")

        # Source/journal
        source = (item.get("primary_location") or {}).get("source") or {}
        if source.get("display_name"):
            lines.append(f"  Journal: {source['display_name']}")

        if item.get("doi"):
            lines.append(f"  DOI: {item['doi']}")

        # Open access PDF
        oa = item.get("open_access") or {}
        if oa.get("oa_url"):
            lines.append(f"  PDF: {oa['oa_url']}")

        lines.append(f"  URL: {item.get('id', '')}")
        lines.append(f"  Type: {item.get('type', 'unknown')}")
        lines.append("")

    return "\n".join(lines)


async def get_work(work_id: str) -> str:
    """Get a work's details from OpenAlex by its OpenAlex ID, DOI, or other identifier."""
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        try:
            resp = await client.get(
                f"{BASE_URL}/works/{work_id}",
                headers=HEADERS,
            )
            resp.raise_for_status()
            item = resp.json()
        except Exception as e:
            return f"OpenAlex error: {e}"

    title = item.get("title", "Untitled") or "Untitled"
    authors = []
    for a in (item.get("authorships") or []):
        name = (a.get("author") or {}).get("display_name", "")
        if name:
            authors.append(name)

    lines = [f"**{title}**"]
    if authors:
        lines.append(f"  Authors: {', '.join(authors)}")
    lines.append(f"  Year: {item.get('publication_year', 'N/A')} | Citations: {item.get('cited_by_count', 0)}")

    source = (item.get("primary_location") or {}).get("source") or {}
    if source.get("display_name"):
        lines.append(f"  Journal: {source['display_name']}")

    if item.get("doi"):
        lines.append(f"  DOI: {item['doi']}")

    oa = item.get("open_access") or {}
    if oa.get("oa_url"):
        lines.append(f"  PDF: {oa['oa_url']}")

    lines.append(f"  URL: {item.get('id', '')}")
    lines.append(f"  Type: {item.get('type', 'unknown')}")

    # Abstract (reconstructed from inverted index)
    abstract_inv = item.get("abstract_inverted_index")
    if abstract_inv:
        try:
            # Reconstruct abstract from inverted index
            word_positions = []
            for word, positions in abstract_inv.items():
                for pos in positions:
                    word_positions.append((pos, word))
            word_positions.sort()
            abstract = " ".join(w for _, w in word_positions)
            lines.append(f"  Abstract: {abstract[:300]}...")
        except Exception:
            pass

    return "\n".join(lines)

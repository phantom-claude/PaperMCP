"""INSPIRE-HEP source — search high energy physics literature.

Uses the free INSPIRE-HEP API (no API key required).
API docs: https://inspirehep.net/help/knowledge-base/inspire-api/
"""

import logging

import httpx

logger = logging.getLogger("paper_mcp.inspirehep")

BASE_URL = "https://inspirehep.net/api/literature"
HEADERS = {"User-Agent": "paper-mcp/0.1.0", "Accept": "application/json"}


async def search(query: str, max_results: int = 10) -> str:
    """Search INSPIRE-HEP for high energy physics literature."""
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        try:
            resp = await client.get(
                BASE_URL,
                params={
                    "q": query,
                    "size": min(max_results, 25),
                    "fields": "titles,authors,abstracts,dois,arxiv_eprints,citation_count,earliest_date",
                },
                headers=HEADERS,
            )
            resp.raise_for_status()
        except Exception as e:
            return f"INSPIRE-HEP error: {e}"

    data = resp.json()
    results = (data.get("hits") or {}).get("hits") or []
    total = (data.get("hits") or {}).get("total", 0)

    if not results:
        return f"No INSPIRE-HEP results for '{query}'."

    lines = [f"INSPIRE-HEP results for '{query}' — {total} total, showing {len(results)}:\n"]
    for item in results:
        lines.extend(_format_paper(item))

    return "\n".join(lines)


def _format_paper(item: dict) -> list[str]:
    """Format a single INSPIRE-HEP result into display lines."""
    lines: list[str] = []

    record_id = item.get("id", "")
    metadata = item.get("metadata") or {}

    # Title
    titles = metadata.get("titles") or []
    title = titles[0].get("title", "N/A") if titles else "N/A"

    # Authors
    author_list = metadata.get("authors") or []
    authors = ", ".join(a.get("full_name", "") for a in author_list[:5])

    # Abstract
    abstracts = metadata.get("abstracts") or []
    abstract = abstracts[0].get("value", "") if abstracts else ""

    # DOI
    dois = metadata.get("dois") or []
    doi = dois[0].get("value", "") if dois else ""

    # arXiv ID
    arxiv_eprints = metadata.get("arxiv_eprints") or []
    arxiv_id = arxiv_eprints[0].get("value", "") if arxiv_eprints else ""

    # Citation count and date
    citation_count = metadata.get("citation_count", 0)
    earliest_date = metadata.get("earliest_date", "N/A")

    # URL
    url = f"https://inspirehep.net/literature/{record_id}" if record_id else "N/A"

    lines.append(f"**{title}**")
    if record_id:
        lines.append(f"  INSPIRE ID: {record_id}")
    if arxiv_id:
        lines.append(f"  arXiv: {arxiv_id}")
    if authors:
        lines.append(f"  Authors: {authors}")
    lines.append(f"  Date: {earliest_date}")
    lines.append(f"  Citations: {citation_count}")
    if abstract:
        if len(abstract) > 200:
            lines.append(f"  Abstract: {abstract[:200]}...")
        else:
            lines.append(f"  Abstract: {abstract}")
    if doi:
        lines.append(f"  DOI: {doi}")
    lines.append(f"  URL: {url}")
    lines.append("")
    return lines

"""CrossRef source — search scholarly metadata by DOI, title, author."""

import logging
from typing import Optional

import httpx

logger = logging.getLogger("paper_mcp.crossref")

BASE_URL = "https://api.crossref.org"
HEADERS = {
    "User-Agent": "paper-mcp/0.1.0 (https://github.com/ScienceAIHub/PaperMCP)",
}


async def search(query: str, max_results: int = 10) -> str:
    """Search CrossRef for scholarly works by keywords."""
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        try:
            resp = await client.get(
                f"{BASE_URL}/works",
                params={"query": query, "rows": min(max_results, 100)},
                headers=HEADERS,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            return f"CrossRef error: {e}"

    items = data.get("message", {}).get("items", [])
    if not items:
        return f"No CrossRef results for '{query}'."

    lines = [f"CrossRef results for '{query}' — {len(items)} works:\n"]
    for item in items:
        title = " ".join(item.get("title", ["Untitled"]))
        authors = []
        for a in item.get("author", []):
            name = f"{a.get('given', '')} {a.get('family', '')}".strip()
            if name:
                authors.append(name)

        lines.append(f"**{title}**")
        if authors:
            lines.append(f"  Authors: {', '.join(authors[:5])}")

        # Year
        issued = item.get("issued", {}).get("date-parts", [[]])
        year = issued[0][0] if issued and issued[0] else None
        if year:
            lines.append(f"  Year: {year}")

        if item.get("container-title"):
            lines.append(f"  Journal: {', '.join(item['container-title'])}")
        if item.get("DOI"):
            lines.append(f"  DOI: {item['DOI']}")
        if item.get("URL"):
            lines.append(f"  URL: {item['URL']}")
        lines.append(f"  Type: {item.get('type', 'unknown')}")
        if item.get("is-referenced-by-count"):
            lines.append(f"  Citations: {item['is-referenced-by-count']}")
        lines.append("")

    return "\n".join(lines)


async def get_by_doi(doi: str) -> str:
    """Get metadata for a work by its DOI."""
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        try:
            resp = await client.get(
                f"{BASE_URL}/works/{doi}",
                headers=HEADERS,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            return f"CrossRef error: {e}"

    item = data.get("message", {})
    if not item:
        return f"No CrossRef entry found for DOI '{doi}'."

    title = " ".join(item.get("title", ["Untitled"]))
    authors = []
    for a in item.get("author", []):
        name = f"{a.get('given', '')} {a.get('family', '')}".strip()
        if name:
            authors.append(name)

    lines = [f"**{title}**"]
    if authors:
        lines.append(f"  Authors: {', '.join(authors)}")

    issued = item.get("issued", {}).get("date-parts", [[]])
    year = issued[0][0] if issued and issued[0] else None
    if year:
        lines.append(f"  Year: {year}")

    if item.get("container-title"):
        lines.append(f"  Journal: {', '.join(item['container-title'])}")
    lines.append(f"  DOI: {item.get('DOI', doi)}")
    if item.get("URL"):
        lines.append(f"  URL: {item['URL']}")
    lines.append(f"  Type: {item.get('type', 'unknown')}")
    if item.get("is-referenced-by-count"):
        lines.append(f"  Citations: {item['is-referenced-by-count']}")
    if item.get("abstract"):
        lines.append(f"  Abstract: {item['abstract'][:300]}...")

    return "\n".join(lines)

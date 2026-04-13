"""DOAJ source — search open access journal articles.

Uses the free DOAJ API (no API key required).
API docs: https://doaj.org/api/v2
"""

import logging
import urllib.parse

import httpx

logger = logging.getLogger("paper_mcp.doaj")

BASE_URL = "https://doaj.org/api/search/articles"
HEADERS = {"User-Agent": "paper-mcp/0.1.0", "Accept": "application/json"}


async def search(query: str, max_results: int = 10) -> str:
    """Search DOAJ for open access journal articles."""
    encoded_query = urllib.parse.quote(query)
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        try:
            resp = await client.get(
                f"{BASE_URL}/{encoded_query}",
                params={
                    "pageSize": min(max_results, 100),
                },
                headers=HEADERS,
            )
            resp.raise_for_status()
        except Exception as e:
            return f"DOAJ error: {e}"

    data = resp.json()
    results = data.get("results") or []
    total = int(data.get("total", 0))

    if not results:
        return f"No DOAJ results for '{query}'."

    lines = [f"DOAJ results for '{query}' — {total} total, showing {len(results)}:\n"]
    for item in results:
        lines.extend(_format_paper(item))

    return "\n".join(lines)


def _format_paper(item: dict) -> list[str]:
    """Format a single DOAJ result into display lines."""
    lines: list[str] = []

    bib = item.get("bibjson") or {}

    # Title
    title = bib.get("title", "N/A")

    # Authors
    author_list = bib.get("author") or []
    if not isinstance(author_list, list):
        author_list = [author_list]
    authors = ", ".join(a.get("name", "") for a in author_list[:5])

    # Year
    year = bib.get("year", "N/A")

    # Journal
    journal = (bib.get("journal") or {}).get("title", "")

    # Abstract
    abstract = bib.get("abstract", "")

    # DOI
    doi = ""
    identifiers = bib.get("identifier") or []
    for ident in identifiers:
        if ident.get("type") == "doi":
            doi = ident.get("id", "")
            break

    # URL
    url = ""
    links = bib.get("link") or []
    for link in links:
        if link.get("url"):
            url = link["url"]
            break
    if not url and doi:
        url = f"https://doi.org/{doi}"
    if not url:
        url = "N/A"

    lines.append(f"**{title}**")
    if authors:
        lines.append(f"  Authors: {authors}")
    lines.append(f"  Year: {year}")
    if journal:
        lines.append(f"  Journal: {journal}")
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

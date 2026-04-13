"""Europe PMC source — search biomedical and life science literature.

Uses the free Europe PMC REST API (no API key required).
API docs: https://europepmc.org/RestfulWebService
"""

import logging
from typing import Optional

import httpx

logger = logging.getLogger("paper_mcp.europepmc")

BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest"
HEADERS = {"User-Agent": "paper-mcp/0.1.0"}


async def search(query: str, max_results: int = 10) -> str:
    """Search Europe PMC for biomedical and life science literature."""
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        try:
            resp = await client.get(
                f"{BASE_URL}/search",
                params={
                    "query": query,
                    "pageSize": min(max_results, 1000),
                    "format": "json",
                    "resultType": "core",
                },
                headers=HEADERS,
            )
            resp.raise_for_status()
        except Exception as e:
            return f"Europe PMC error: {e}"

    data = resp.json()
    results = (data.get("resultList") or {}).get("result") or []
    total = int(data.get("hitCount", 0))

    if not results:
        return f"No Europe PMC results for '{query}'."

    lines = [f"Europe PMC results for '{query}' — {total} total, showing {len(results)}:\n"]
    for item in results:
        lines.extend(_format_paper(item))

    return "\n".join(lines)


def _format_paper(item: dict) -> list[str]:
    """Format a single Europe PMC result into display lines."""
    lines: list[str] = []

    # Authors
    author_list = (item.get("authorList") or {}).get("author") or []
    if not isinstance(author_list, list):
        author_list = [author_list]
    authors = ", ".join(
        a.get("fullName") or f"{a.get('firstName', '')} {a.get('lastName', '')}".strip()
        for a in author_list[:5]
    )

    pmid = item.get("pmid", "")
    pmcid = item.get("pmcid", "")
    doi = item.get("doi", "")

    # URL
    if pmcid:
        url = f"https://europepmc.org/article/PMC/{pmcid}"
    elif pmid:
        url = f"https://europepmc.org/article/MED/{pmid}"
    else:
        url = "N/A"

    lines.append(f"**{item.get('title', 'N/A')}**")
    if pmid:
        lines.append(f"  PMID: {pmid}")
    if pmcid:
        lines.append(f"  PMCID: {pmcid}")
    if authors:
        lines.append(f"  Authors: {authors}")
    lines.append(f"  Year: {item.get('pubYear', 'N/A')}")
    if item.get("journalTitle"):
        lines.append(f"  Journal: {item['journalTitle']}")
    lines.append(f"  Citations: {item.get('citedByCount', 0)}")
    if item.get("abstractText"):
        abstract = item["abstractText"]
        if len(abstract) > 200:
            lines.append(f"  Abstract: {abstract[:200]}...")
        else:
            lines.append(f"  Abstract: {abstract}")
    if doi:
        lines.append(f"  DOI: {doi}")
    lines.append(f"  URL: {url}")
    lines.append("")
    return lines

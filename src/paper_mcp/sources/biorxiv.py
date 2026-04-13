"""bioRxiv/medRxiv source — search preprints in biology and medicine.

Uses the free bioRxiv API (no API key required).
API docs: https://api.biorxiv.org/
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx

logger = logging.getLogger("paper_mcp.biorxiv")

BASE_URL = "https://api.biorxiv.org"
HEADERS = {"User-Agent": "paper-mcp/0.1.0"}


def _format_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


async def search(query: str, max_results: int = 10, server: str = "biorxiv") -> str:
    """Search bioRxiv or medRxiv for preprints matching query.

    Args:
        query: Search keywords (matched against title, authors, category, abstract).
        max_results: Maximum results to return.
        server: 'biorxiv' or 'medrxiv'.
    """
    if server not in ("biorxiv", "medrxiv"):
        server = "biorxiv"

    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)

    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        try:
            resp = await client.get(
                f"{BASE_URL}/details/{server}/{_format_date(start_date)}/{_format_date(end_date)}/0/json",
                headers=HEADERS,
            )
            resp.raise_for_status()
        except Exception as e:
            return f"{server} error: {e}"

    collection = resp.json().get("collection") or []

    # Filter by query
    query_lower = query.lower()
    filtered = [
        item for item in collection
        if query_lower in (item.get("title") or "").lower()
        or query_lower in (item.get("authors") or "").lower()
        or query_lower in (item.get("category") or "").lower()
        or query_lower in (item.get("abstract") or "").lower()
    ]

    if not filtered:
        return f"No {server} results for '{query}' in the last 90 days."

    papers = filtered[:max_results]
    lines = [f"{server} results for '{query}' — {len(filtered)} found, showing {len(papers)}:\n"]
    for item in papers:
        doi = item.get("doi", "")
        url = f"https://www.{server}.org/content/{doi}" if doi else "N/A"
        pdf_url = f"https://www.{server}.org/content/{doi}.full.pdf" if doi else ""

        lines.append(f"**{item.get('title', 'N/A')}**")
        lines.append(f"  DOI: {doi}")
        # Truncate by author count, not character count
        authors = item.get("authors") or "N/A"
        author_list = authors.split(";")
        if len(author_list) > 5:
            lines.append(f"  Authors: {'; '.join(a.strip() for a in author_list[:5])}; ...")
        else:
            lines.append(f"  Authors: {authors}")
        lines.append(f"  Date: {item.get('date', 'N/A')}")
        if item.get("category"):
            lines.append(f"  Category: {item['category']}")
        if item.get("abstract"):
            abstract = item["abstract"]
            if len(abstract) > 200:
                lines.append(f"  Abstract: {abstract[:200]}...")
            else:
                lines.append(f"  Abstract: {abstract}")
        lines.append(f"  URL: {url}")
        if pdf_url:
            lines.append(f"  PDF: {pdf_url}")
        lines.append("")

    return "\n".join(lines)

"""Zenodo source — search open research data and publications.

Uses the free Zenodo API (no API key required).
API docs: https://developers.zenodo.org/
"""

from __future__ import annotations

import re
from typing import Any

import httpx

BASE_URL = "https://zenodo.org/api/records"
HEADERS = {
    "User-Agent": "paper-mcp/0.1.0",
    "Accept": "application/json",
}


def _strip_html(text: str) -> str:
    """Remove HTML tags from *text*."""
    return re.sub(r"<[^>]+>", "", text)


def _format_paper(hit: dict[str, Any]) -> str:
    """Return a human-readable summary for a single Zenodo record."""
    meta = hit.get("metadata", {})

    title = meta.get("title", "Unknown title")
    creators = meta.get("creators", [])
    authors = ", ".join(c.get("name", "Unknown") for c in creators) if creators else "Unknown"
    description = _strip_html(meta.get("description", "")).strip()
    if len(description) > 500:
        description = description[:500] + "…"
    doi = meta.get("doi", "N/A")
    pub_date = meta.get("publication_date", "N/A")
    resource_type = meta.get("resource_type", {}).get("title", "N/A")
    access_right = meta.get("access_right", "N/A")

    record_id = hit.get("id", "")
    url = f"https://zenodo.org/records/{record_id}" if record_id else "N/A"

    # Try to find a PDF link in the files list
    pdf_link = "N/A"
    for f in hit.get("files", []):
        file_self = (f.get("links") or {}).get("self", "")
        if file_self:
            pdf_link = file_self
            break

    # Related identifiers
    related = meta.get("related_identifiers", [])
    related_str = ""
    if related:
        related_items = [
            f"  - {r.get('identifier', 'N/A')} ({r.get('relation', 'N/A')})"
            for r in related[:5]
        ]
        related_str = "\nRelated identifiers:\n" + "\n".join(related_items)

    return (
        f"Title: {title}\n"
        f"Authors: {authors}\n"
        f"Date: {pub_date}\n"
        f"Type: {resource_type}\n"
        f"Access: {access_right}\n"
        f"DOI: {doi}\n"
        f"URL: {url}\n"
        f"PDF: {pdf_link}\n"
        f"Description: {description}"
        f"{related_str}"
    )


async def search(query: str, max_results: int = 10) -> str:
    """Search Zenodo for *query* and return formatted results."""
    size = min(max(max_results, 1), 100)
    params: dict[str, Any] = {
        "q": query,
        "size": size,
        "type": "publication",
        "sort": "mostrecent",
    }

    async with httpx.AsyncClient(headers=HEADERS, timeout=30) as client:
        resp = await client.get(BASE_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    hits: list[dict[str, Any]] = data.get("hits", {}).get("hits", [])
    if not hits:
        return f"No Zenodo results for '{query}'."

    parts = [_format_paper(hit) for hit in hits]
    header = f"Zenodo results for '{query}' ({len(parts)} of {data.get('hits', {}).get('total', '?')}):\n"
    return header + "\n\n---\n\n".join(parts)

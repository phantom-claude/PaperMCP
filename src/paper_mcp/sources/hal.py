"""HAL source — search France national open archive.

Uses the free HAL API (no API key required).
API docs: https://api.archives-ouvertes.fr/docs/search
"""

import logging

import httpx

logger = logging.getLogger("paper_mcp.hal")

BASE_URL = "https://api.archives-ouvertes.fr/search/"
HEADERS = {"User-Agent": "paper-mcp/0.1.0", "Accept": "application/json"}


async def search(query: str, max_results: int = 10) -> str:
    """Search HAL for French and international research publications."""
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        try:
            resp = await client.get(
                BASE_URL,
                params={
                    "q": query,
                    "rows": min(max_results, 100),
                    "wt": "json",
                    "fl": "halId_s,title_s,authFullName_s,abstract_s,doiId_s,publicationDateY_i,uri_s,docType_s,fileMain_s",
                    "sort": "score desc",
                },
                headers=HEADERS,
            )
            resp.raise_for_status()
        except Exception as e:
            return f"HAL error: {e}"

    data = resp.json()
    results = (data.get("response") or {}).get("docs") or []
    total = (data.get("response") or {}).get("numFound", 0)

    if not results:
        return f"No HAL results for '{query}'."

    lines = [f"HAL results for '{query}' — {total} total, showing {len(results)}:\n"]
    for item in results:
        lines.extend(_format_paper(item))

    return "\n".join(lines)


def _format_paper(item: dict) -> list[str]:
    """Format a single HAL result into display lines."""
    lines: list[str] = []

    # Title may be a list or a string
    title = item.get("title_s", "N/A")
    if isinstance(title, list):
        title = title[0] if title else "N/A"

    # Authors
    authors_list = item.get("authFullName_s") or []
    if not isinstance(authors_list, list):
        authors_list = [authors_list]
    authors = ", ".join(authors_list[:5])

    hal_id = item.get("halId_s", "")
    doi = item.get("doiId_s", "")
    year = item.get("publicationDateY_i", "N/A")
    doc_type = item.get("docType_s", "")
    url = item.get("uri_s") or (f"https://hal.science/{hal_id}" if hal_id else "N/A")
    pdf_url = item.get("fileMain_s", "")

    # Abstract may be a list or a string
    abstract = item.get("abstract_s", "")
    if isinstance(abstract, list):
        abstract = abstract[0] if abstract else ""

    lines.append(f"**{title}**")
    if hal_id:
        lines.append(f"  HAL ID: {hal_id}")
    if authors:
        lines.append(f"  Authors: {authors}")
    lines.append(f"  Year: {year}")
    if doc_type:
        lines.append(f"  Type: {doc_type}")
    if abstract:
        if len(abstract) > 200:
            lines.append(f"  Abstract: {abstract[:200]}...")
        else:
            lines.append(f"  Abstract: {abstract}")
    if doi:
        lines.append(f"  DOI: {doi}")
    lines.append(f"  URL: {url}")
    if pdf_url:
        lines.append(f"  PDF: {pdf_url}")
    lines.append("")
    return lines

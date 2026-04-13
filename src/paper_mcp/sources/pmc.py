"""PMC source — search PubMed Central full-text open access articles.

Uses the free NCBI E-utilities API (no API key required).
API docs: https://www.ncbi.nlm.nih.gov/pmc/tools/developers/
"""

import logging

import httpx

logger = logging.getLogger("paper_mcp.pmc")

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
HEADERS = {"User-Agent": "paper-mcp/0.1.0"}


async def search(query: str, max_results: int = 10) -> str:
    """Search PubMed Central for full-text open access articles."""
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        # Step 1: Search for PMC IDs
        try:
            resp = await client.get(
                ESEARCH_URL,
                params={
                    "db": "pmc",
                    "term": query,
                    "retmax": max_results,
                    "retmode": "json",
                    "tool": "paper-mcp",
                    "email": "papermcp@example.com",
                },
                headers=HEADERS,
            )
            resp.raise_for_status()
        except Exception as e:
            return f"PMC error: {e}"

        data = resp.json()
        id_list = (data.get("esearchresult") or {}).get("idlist") or []

        if not id_list:
            return f"No PMC results for '{query}'."

        # Step 2: Fetch summaries for the IDs
        try:
            resp = await client.get(
                ESUMMARY_URL,
                params={
                    "db": "pmc",
                    "id": ",".join(id_list),
                    "retmode": "json",
                    "tool": "paper-mcp",
                    "email": "papermcp@example.com",
                },
                headers=HEADERS,
            )
            resp.raise_for_status()
        except Exception as e:
            return f"PMC error: {e}"

    data = resp.json()
    result = data.get("result") or {}

    papers = []
    for pmc_id in id_list:
        item = result.get(pmc_id)
        if item:
            papers.append(item)

    if not papers:
        return f"No PMC results for '{query}'."

    lines = [f"PMC results for '{query}' — showing {len(papers)}:\n"]
    for item in papers:
        lines.extend(_format_paper(item))

    return "\n".join(lines)


def _format_paper(item: dict) -> list[str]:
    """Format a single PMC result into display lines."""
    lines: list[str] = []

    # Authors
    author_list = item.get("authors") or []
    if not isinstance(author_list, list):
        author_list = [author_list]
    authors = ", ".join(a.get("name", "") for a in author_list[:5])
    if not authors:
        authors = item.get("sortfirstauthor", "")

    uid = item.get("uid", "")
    pmcid = item.get("pmcid", "") or f"PMC{uid}"

    # Extract DOI from articleids if available
    doi = ""
    for aid in item.get("articleids") or []:
        if aid.get("idtype") == "doi":
            doi = aid.get("value", "")
            break

    pmc_number = pmcid.replace("PMC", "") if pmcid.startswith("PMC") else uid
    url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_number}/"
    pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_number}/pdf/"

    lines.append(f"**{item.get('title', 'N/A')}**")
    if pmcid:
        lines.append(f"  PMCID: {pmcid}")
    if authors:
        lines.append(f"  Authors: {authors}")
    lines.append(f"  Date: {item.get('pubdate', 'N/A')}")
    if item.get("fulljournalname"):
        lines.append(f"  Journal: {item['fulljournalname']}")
    if doi:
        lines.append(f"  DOI: {doi}")
    lines.append(f"  URL: {url}")
    lines.append(f"  PDF: {pdf_url}")
    lines.append("")
    return lines

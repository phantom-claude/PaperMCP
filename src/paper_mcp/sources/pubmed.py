"""PubMed source — search biomedical literature via NCBI E-utilities.

Uses the free NCBI E-utilities API (no API key required, 3 req/s without key).
API docs: https://www.ncbi.nlm.nih.gov/books/NBK25500/
"""

import logging
from typing import Optional
from xml.etree import ElementTree

import httpx

logger = logging.getLogger("paper_mcp.pubmed")

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
HEADERS = {"User-Agent": "paper-mcp/0.1.0"}


def _parse_article(article_elem) -> dict:
    """Parse a single PubmedArticle XML element into a dict."""
    info: dict = {}

    medline = article_elem.find(".//MedlineCitation")
    if medline is None:
        return info

    pmid_elem = medline.find("PMID")
    info["pmid"] = pmid_elem.text if pmid_elem is not None else ""

    article = medline.find("Article")
    if article is None:
        return info

    title_elem = article.find("ArticleTitle")
    info["title"] = (title_elem.text or "") if title_elem is not None else ""

    # Abstract
    abstract_parts = []
    abstract_elem = article.find("Abstract")
    if abstract_elem is not None:
        for at in abstract_elem.findall("AbstractText"):
            label = at.get("Label", "")
            text = "".join(at.itertext())
            if label:
                abstract_parts.append(f"{label}: {text}")
            else:
                abstract_parts.append(text)
    info["abstract"] = " ".join(abstract_parts)

    # Authors
    authors = []
    author_list = article.find("AuthorList")
    if author_list is not None:
        for author in author_list.findall("Author"):
            last = author.findtext("LastName", "")
            fore = author.findtext("ForeName", "")
            name = f"{fore} {last}".strip()
            if name:
                authors.append(name)
    info["authors"] = authors

    # Journal
    journal = article.find("Journal")
    if journal is not None:
        info["journal"] = journal.findtext("Title", "")
        pub_date = journal.find(".//PubDate")
        if pub_date is not None:
            year = pub_date.findtext("Year", "")
            info["year"] = year

    # DOI
    pubmed_data = article_elem.find("PubmedData")
    if pubmed_data is not None:
        for aid in pubmed_data.findall(".//ArticleId"):
            if aid.get("IdType") == "doi":
                info["doi"] = aid.text or ""
                break

    return info


async def search(query: str, max_results: int = 10) -> str:
    """Search PubMed for biomedical papers."""
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        try:
            # Step 1: Search for PMIDs
            resp = await client.get(
                f"{BASE_URL}/esearch.fcgi",
                params={
                    "db": "pubmed",
                    "term": query,
                    "retmax": min(max_results, 200),
                    "retmode": "json",
                },
                headers=HEADERS,
            )
            resp.raise_for_status()
        except Exception as e:
            return f"PubMed search error: {e}"

    search_data = resp.json()
    id_list = (search_data.get("esearchresult") or {}).get("idlist") or []
    total = int((search_data.get("esearchresult") or {}).get("count", "0"))

    if not id_list:
        return f"No PubMed results for '{query}'."

    # Step 2: Fetch paper details
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        try:
            resp = await client.get(
                f"{BASE_URL}/efetch.fcgi",
                params={
                    "db": "pubmed",
                    "id": ",".join(id_list),
                    "retmode": "xml",
                },
                headers=HEADERS,
            )
            resp.raise_for_status()
        except Exception as e:
            return f"PubMed fetch error: {e}"

    # Parse XML
    try:
        root = ElementTree.fromstring(resp.text)
    except ElementTree.ParseError:
        return "Error parsing PubMed response."

    articles = root.findall(".//PubmedArticle")
    if not articles:
        return f"No PubMed results for '{query}'."

    lines = [f"PubMed results for '{query}' — {total} total, showing {len(articles)}:\n"]
    for article_elem in articles:
        p = _parse_article(article_elem)
        if not p.get("title"):
            continue

        authors_str = ", ".join(p.get("authors", [])[:5])
        lines.append(f"**{p['title']}**")
        lines.append(f"  PMID: {p.get('pmid', 'N/A')}")
        if authors_str:
            lines.append(f"  Authors: {authors_str}")
        lines.append(f"  Year: {p.get('year', 'N/A')}")
        if p.get("journal"):
            lines.append(f"  Journal: {p['journal']}")
        if p.get("abstract"):
            abstract = p["abstract"]
            if len(abstract) > 200:
                lines.append(f"  Abstract: {abstract[:200]}...")
            else:
                lines.append(f"  Abstract: {abstract}")
        lines.append(f"  URL: https://pubmed.ncbi.nlm.nih.gov/{p.get('pmid', '')}/")
        if p.get("doi"):
            lines.append(f"  DOI: {p['doi']}")
        lines.append("")

    return "\n".join(lines)

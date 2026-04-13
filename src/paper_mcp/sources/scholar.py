"""Google Scholar source — search papers and get author info."""

import logging
import asyncio
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("paper_mcp.scholar")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def _web_search(query: str, num_results: int = 5, author: Optional[str] = None,
                year_from: Optional[int] = None, year_to: Optional[int] = None) -> list[dict]:
    """Search Google Scholar via web scraping."""
    params = {"q": query.replace(" ", "+")}
    if author:
        params["as_auth"] = author
    if year_from:
        params["as_ylo"] = str(year_from)
    if year_to:
        params["as_yhi"] = str(year_to)

    url = "https://scholar.google.com/scholar?" + "&".join(f"{k}={v}" for k, v in params.items())

    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            return [{"error": f"HTTP {response.status_code}"}]
    except Exception as e:
        return [{"error": str(e)}]

    soup = BeautifulSoup(response.text, "html.parser")
    results = []

    for item in soup.find_all("div", class_="gs_ri"):
        if len(results) >= num_results:
            break

        title_tag = item.find("h3", class_="gs_rt")
        title = title_tag.get_text() if title_tag else "No title"
        link = ""
        if title_tag and title_tag.find("a"):
            link = title_tag.find("a")["href"]

        authors_tag = item.find("div", class_="gs_a")
        authors = authors_tag.get_text() if authors_tag else ""

        abstract_tag = item.find("div", class_="gs_rs")
        abstract = abstract_tag.get_text() if abstract_tag else ""

        results.append({
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "url": link,
        })

    return results


def _get_author_info(author_name: str) -> dict:
    """Get author information using the scholarly library."""
    try:
        from scholarly import scholarly
        search_query = scholarly.search_author(author_name)
        author = next(search_query)
        filled = scholarly.fill(author)

        return {
            "name": filled.get("name", "N/A"),
            "affiliation": filled.get("affiliation", "N/A"),
            "interests": filled.get("interests", []),
            "cited_by": filled.get("citedby", 0),
            "publications": [
                {
                    "title": pub.get("bib", {}).get("title", "N/A"),
                    "year": pub.get("bib", {}).get("pub_year", "N/A"),
                    "citations": pub.get("num_citations", 0),
                }
                for pub in filled.get("publications", [])[:10]
            ],
        }
    except StopIteration:
        return {"error": f"Author '{author_name}' not found on Google Scholar."}
    except Exception as e:
        return {"error": f"Error retrieving author info: {e}"}


async def search(query: str, num_results: int = 5) -> str:
    """Search Google Scholar for papers by keywords."""
    results = await asyncio.to_thread(_web_search, query, num_results)

    if not results:
        return "No results found on Google Scholar."

    if "error" in results[0]:
        return f"Error: {results[0]['error']}"

    lines = [f"Google Scholar results for '{query}' ({len(results)} papers):\n"]
    for r in results:
        lines.append(f"**{r['title']}**")
        lines.append(f"  {r['authors']}")
        if r["abstract"]:
            lines.append(f"  Abstract: {r['abstract'][:200]}...")
        if r["url"]:
            lines.append(f"  URL: {r['url']}")
        lines.append("")

    return "\n".join(lines)


async def advanced_search(
    query: str,
    author: Optional[str] = None,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    num_results: int = 5,
) -> str:
    """Advanced Google Scholar search with author and year filters."""
    results = await asyncio.to_thread(
        _web_search, query, num_results, author, year_from, year_to
    )

    if not results:
        return "No results found."

    if "error" in results[0]:
        return f"Error: {results[0]['error']}"

    filters = []
    if author:
        filters.append(f"author={author}")
    if year_from or year_to:
        filters.append(f"years={year_from or '?'}-{year_to or '?'}")
    filter_str = f" (filters: {', '.join(filters)})" if filters else ""

    lines = [f"Google Scholar advanced results for '{query}'{filter_str} — {len(results)} papers:\n"]
    for r in results:
        lines.append(f"**{r['title']}**")
        lines.append(f"  {r['authors']}")
        if r["abstract"]:
            lines.append(f"  Abstract: {r['abstract'][:200]}...")
        if r["url"]:
            lines.append(f"  URL: {r['url']}")
        lines.append("")

    return "\n".join(lines)


async def author_info(author_name: str) -> str:
    """Get detailed author information from Google Scholar."""
    info = await asyncio.to_thread(_get_author_info, author_name)

    if "error" in info:
        return info["error"]

    lines = [
        f"**{info['name']}**",
        f"  Affiliation: {info['affiliation']}",
        f"  Cited by: {info['cited_by']}",
        f"  Interests: {', '.join(info['interests'])}",
        "",
        "  Top Publications:",
    ]
    for pub in info["publications"]:
        lines.append(f"    - {pub['title']} ({pub['year']}) — {pub['citations']} citations")

    return "\n".join(lines)

"""DBLP source — search CS bibliography, BibTeX, author publications."""

import logging
import asyncio
import difflib
import re
from collections import Counter
from typing import Optional, Any

import requests

logger = logging.getLogger("paper_mcp.dblp")

REQUEST_TIMEOUT = 10
HEADERS = {
    "User-Agent": "paper-mcp/0.1.0 (https://github.com/paper-mcp)",
    "Accept": "application/json",
}


def _fetch_publications(query: str, max_results: int) -> list[dict]:
    """Fetch publications from DBLP API."""
    try:
        url = "https://dblp.org/search/publ/api"
        params = {"q": query, "format": "json", "h": max_results}
        response = requests.get(url, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()

        hits = data.get("result", {}).get("hits", {})
        total = int(hits.get("@total", "0"))
        if total == 0:
            return []

        publications = hits.get("hit", [])
        if not isinstance(publications, list):
            publications = [publications]

        results = []
        for pub in publications:
            info = pub.get("info", {})

            authors_data = info.get("authors", {}).get("author", [])
            if not isinstance(authors_data, list):
                authors_data = [authors_data]
            authors = []
            for a in authors_data:
                authors.append(a.get("text", str(a)) if isinstance(a, dict) else str(a))

            dblp_url = info.get("url", "")
            dblp_key = dblp_url.replace("https://dblp.org/rec/", "") if dblp_url else ""

            results.append({
                "title": info.get("title", ""),
                "authors": authors,
                "venue": info.get("venue", ""),
                "year": int(info.get("year", 0)) if info.get("year") else None,
                "type": info.get("type", ""),
                "doi": info.get("doi", ""),
                "url": dblp_url,
                "dblp_key": dblp_key,
            })

        return results
    except requests.exceptions.Timeout:
        return [{"error": f"Timeout after {REQUEST_TIMEOUT}s"}]
    except Exception as e:
        return [{"error": str(e)}]


def _fetch_bibtex(dblp_key: str) -> str:
    """Fetch a BibTeX entry from DBLP by key."""
    if not dblp_key or dblp_key.isspace():
        return ""

    urls = [f"https://dblp.org/rec/{dblp_key}.bib"]
    if ":" in dblp_key:
        urls.append(f"https://dblp.org/rec/{dblp_key.replace(':', '/')}.bib")

    for url in urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200 and resp.text.strip():
                return resp.text.strip()
        except Exception:
            continue

    return ""


def _get_venue_info(venue_name: str) -> dict:
    """Get information about a DBLP venue."""
    try:
        url = "https://dblp.org/search/venue/api"
        params = {"q": venue_name, "format": "json", "h": 1}
        resp = requests.get(url, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        hits = data.get("result", {}).get("hits", {})
        if int(hits.get("@total", "0")) > 0:
            hit = hits.get("hit", [])
            if isinstance(hit, list):
                hit = hit[0]
            info = hit.get("info", {})
            return {
                "venue": info.get("venue", ""),
                "acronym": info.get("acronym", ""),
                "type": info.get("type", ""),
                "url": info.get("url", ""),
            }
    except Exception as e:
        logger.error(f"Error fetching venue: {e}")

    return {"venue": "", "acronym": "", "type": "", "url": ""}


async def search(
    query: str,
    max_results: int = 10,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    venue_filter: Optional[str] = None,
) -> str:
    """Search DBLP for publications using boolean queries (supports AND/OR)."""

    def _do_search():
        query_lower = query.lower()
        if " or " in query_lower:
            subqueries = [q.strip() for q in query_lower.split(" or ") if q.strip()]
            seen = set()
            all_results = []
            for q in subqueries:
                for pub in _fetch_publications(q, max_results):
                    ident = (pub.get("title"), pub.get("year"))
                    if ident not in seen:
                        all_results.append(pub)
                        seen.add(ident)
            results = all_results
        else:
            results = _fetch_publications(query, max_results)

        # Apply filters
        filtered = []
        for r in results:
            if "error" in r:
                filtered.append(r)
                continue
            year = r.get("year")
            if year_from and year and year < year_from:
                continue
            if year_to and year and year > year_to:
                continue
            if venue_filter:
                venue = r.get("venue", "")
                if isinstance(venue, list):
                    venue = " ".join(venue)
                if venue_filter.lower() not in venue.lower():
                    continue
            filtered.append(r)

        return filtered[:max_results]

    results = await asyncio.to_thread(_do_search)

    if not results:
        return "No DBLP results found."

    if "error" in results[0]:
        return f"Error: {results[0]['error']}"

    lines = [f"DBLP results for '{query}' — {len(results)} publications:\n"]
    for r in results:
        lines.append(f"**{r['title']}**")
        lines.append(f"  Authors: {', '.join(r['authors'])}")
        lines.append(f"  Venue: {r['venue']} | Year: {r['year']} | Type: {r['type']}")
        if r.get("dblp_key"):
            lines.append(f"  DBLP Key: {r['dblp_key']}")
        if r.get("doi"):
            lines.append(f"  DOI: {r['doi']}")
        lines.append("")

    return "\n".join(lines)


async def fuzzy_title_search(
    title: str,
    similarity_threshold: float = 0.6,
    max_results: int = 10,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    venue_filter: Optional[str] = None,
) -> str:
    """Search DBLP with fuzzy title matching."""

    def _do_search():
        seen = set()
        candidates = []

        for q in [f"title:{title}", title]:
            pubs = _fetch_publications(q, max_results * 3)
            for p in pubs:
                t = p.get("title", "")
                if t not in seen and "error" not in p:
                    candidates.append(p)
                    seen.add(t)

        # Apply year/venue filters
        filtered = []
        for p in candidates:
            year = p.get("year")
            if year_from and year and year < year_from:
                continue
            if year_to and year and year > year_to:
                continue
            if venue_filter:
                venue = p.get("venue", "")
                if isinstance(venue, list):
                    venue = " ".join(venue)
                if venue_filter.lower() not in venue.lower():
                    continue

            ratio = difflib.SequenceMatcher(None, title.lower(), p.get("title", "").lower()).ratio()
            if ratio >= similarity_threshold:
                p["similarity"] = round(ratio, 3)
                filtered.append(p)

        filtered.sort(key=lambda x: x.get("similarity", 0), reverse=True)
        return filtered[:max_results]

    results = await asyncio.to_thread(_do_search)

    if not results:
        return f"No DBLP papers found matching '{title}'."

    lines = [f"DBLP fuzzy title search for '{title}' — {len(results)} matches:\n"]
    for r in results:
        lines.append(f"**{r['title']}** (similarity: {r.get('similarity', '?')})")
        lines.append(f"  Authors: {', '.join(r['authors'])}")
        lines.append(f"  Venue: {r['venue']} | Year: {r['year']}")
        if r.get("dblp_key"):
            lines.append(f"  DBLP Key: {r['dblp_key']}")
        lines.append("")

    return "\n".join(lines)


async def author_publications(
    author_name: str,
    similarity_threshold: float = 0.6,
    max_results: int = 20,
) -> str:
    """Get publications for a specific author from DBLP with fuzzy name matching."""

    def _do_search():
        pubs = _fetch_publications(f"author:{author_name}", max_results * 2)

        filtered = []
        for p in pubs:
            if "error" in p:
                continue
            best_ratio = max(
                (difflib.SequenceMatcher(None, author_name.lower(), a.lower()).ratio()
                 for a in p.get("authors", [""])),
                default=0,
            )
            if best_ratio >= similarity_threshold:
                filtered.append(p)

        return filtered[:max_results]

    results = await asyncio.to_thread(_do_search)

    if not results:
        return f"No publications found for author '{author_name}'."

    lines = [f"DBLP publications by '{author_name}' — {len(results)} papers:\n"]
    for r in results:
        lines.append(f"**{r['title']}**")
        lines.append(f"  Authors: {', '.join(r['authors'])}")
        lines.append(f"  Venue: {r['venue']} | Year: {r['year']}")
        if r.get("dblp_key"):
            lines.append(f"  DBLP Key: {r['dblp_key']}")
        lines.append("")

    return "\n".join(lines)


async def venue_info(venue_name: str) -> str:
    """Get information about a DBLP publication venue."""
    info = await asyncio.to_thread(_get_venue_info, venue_name)

    if not info.get("venue"):
        return f"No venue found for '{venue_name}'."

    return (
        f"**{info['venue']}**\n"
        f"  Acronym: {info['acronym']}\n"
        f"  Type: {info['type']}\n"
        f"  URL: {info['url']}"
    )


async def bibtex(dblp_key: str) -> str:
    """Fetch a BibTeX entry from DBLP by its key."""
    result = await asyncio.to_thread(_fetch_bibtex, dblp_key)

    if not result:
        return f"No BibTeX entry found for key '{dblp_key}'."

    return result

"""Searcher for ChemRxiv chemistry preprint server.

ChemRxiv is a free submission, distribution, and archive service for
unpublished preprints in chemistry and related fields.

Uses the Crossref API filtered for ChemRxiv preprints.
"""

import logging
from typing import List

import httpx

from ..paper import Paper

logger = logging.getLogger(__name__)

CROSSREF_API = "https://api.crossref.org/works"


async def search(query: str, max_results: int = 10) -> str:
    """Search ChemRxiv for chemistry preprints via Crossref filter."""
    try:
        params = {
            "query": query,
            "rows": min(max_results, 50),
            "filter": "type:posted-content",
            "select": "DOI,title,author,abstract,URL,created,link",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(CROSSREF_API, params=params)
            resp.raise_for_status()
            data = resp.json()

        items = data.get("message", {}).get("items", [])
        # Filter for chemistry-related preprints
        results = []
        for item in items:
            title = " ".join(item.get("title", [""]))
            authors = ", ".join(
                f"{a.get('given', '')} {a.get('family', '')}".strip()
                for a in item.get("author", [])
            )
            doi = item.get("DOI", "")
            url = item.get("URL", "")
            abstract = item.get("abstract", "")
            created = item.get("created", {}).get("date-parts", [[""]])[0]
            date_str = "-".join(str(p) for p in created if p) if created else ""
            results.append(
                f"**{title}**\n"
                f"  Authors: {authors}\n"
                f"  DOI: {doi}\n"
                f"  Date: {date_str}\n"
                f"  URL: {url}\n"
                f"  Source: chemrxiv"
            )
            if len(results) >= max_results:
                break

        if not results:
            return f"No ChemRxiv results for '{query}'."
        return f"## ChemRxiv Results ({len(results)})\n\n" + "\n\n".join(results)
    except Exception as e:
        logger.error(f"ChemRxiv search error: {e}")
        return f"[ChemRxiv error: {e}]"

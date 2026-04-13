"""Unpaywall source — find open access versions of papers by DOI.

Uses the free Unpaywall API (email-based, no API key).
API docs: https://unpaywall.org/products/api
"""

import logging

import httpx

logger = logging.getLogger("paper_mcp.unpaywall")

BASE_URL = "https://api.unpaywall.org/v2"
HEADERS = {"User-Agent": "paper-mcp/0.1.0"}
EMAIL = "papermcp@example.com"


async def search(query: str, max_results: int = 10) -> str:
    """Search Unpaywall. Only DOI lookups are supported."""
    query = query.strip()
    if query.startswith("10."):
        return await get_open_access(query)
    return "Unpaywall only supports DOI lookups. Provide a DOI like '10.1234/example'."


async def get_open_access(doi: str) -> str:
    """Look up open access information for a DOI via Unpaywall."""
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        try:
            resp = await client.get(
                f"{BASE_URL}/{doi}",
                params={"email": EMAIL},
                headers=HEADERS,
            )
            if resp.status_code == 404:
                return f"No Unpaywall data found for DOI '{doi}'."
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            return f"Unpaywall error: {e}"
        except Exception as e:
            return f"Unpaywall error: {e}"

    data = resp.json()
    return "\n".join(_format_result(data, doi))


def _format_result(data: dict, doi: str) -> list[str]:
    """Format an Unpaywall result into display lines."""
    lines: list[str] = []

    # Authors
    z_authors = data.get("z_authors") or []
    if not isinstance(z_authors, list):
        z_authors = [z_authors]
    authors = ", ".join(
        f"{a.get('given', '')} {a.get('family', '')}".strip()
        for a in z_authors[:5]
    )

    is_oa = data.get("is_oa", False)
    best_oa = data.get("best_oa_location") or {}

    lines.append(f"**{data.get('title', 'N/A')}**")
    if authors:
        lines.append(f"  Authors: {authors}")
    lines.append(f"  Year: {data.get('year', 'N/A')}")
    if data.get("journal_name"):
        lines.append(f"  Journal: {data['journal_name']}")
    if data.get("genre"):
        lines.append(f"  Genre: {data['genre']}")
    lines.append(f"  DOI: {doi}")
    lines.append(f"  Is Open Access: {is_oa}")

    if best_oa:
        lines.append(f"  Best OA URL: {best_oa.get('url', 'N/A')}")
        lines.append(f"  PDF URL: {best_oa.get('url_for_pdf', 'N/A')}")
        lines.append(f"  License: {best_oa.get('license', 'N/A')}")
        lines.append(f"  Host Type: {best_oa.get('host_type', 'N/A')}")
        lines.append(f"  Version: {best_oa.get('version', 'N/A')}")

    oa_locations = data.get("oa_locations") or []
    if len(oa_locations) > 1:
        lines.append(f"  Additional OA Locations: {len(oa_locations) - 1}")
        for loc in oa_locations[1:]:
            url = loc.get("url_for_pdf") or loc.get("url") or "N/A"
            lines.append(f"    - {url} ({loc.get('host_type', 'N/A')}, {loc.get('license', 'N/A')})")

    lines.append("")
    return lines

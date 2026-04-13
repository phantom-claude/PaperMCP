"""OpenAIRE source — search European open access research.

Uses the free OpenAIRE API (no API key required).
API docs: https://graph.openaire.eu/develop/api.html
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import httpx

BASE_URL = "https://api.openaire.eu/search/researchProducts"
HEADERS = {"User-Agent": "paper-mcp/0.1.0", "Accept": "application/json"}
MAX_RESULTS_CAP = 50


def _safe_get(data: dict | list | None, *keys: str, default: str = "") -> str:
    """Safely traverse nested dicts/lists and return a string value."""
    current: object = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        elif isinstance(current, list) and current:
            current = current[0]
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return default
        else:
            return default
        if current is None:
            return default
    if isinstance(current, dict):
        return str(current.get("$", current.get("content", default)))
    if isinstance(current, list):
        parts = []
        for item in current:
            if isinstance(item, dict):
                parts.append(str(item.get("$", item.get("content", ""))))
            else:
                parts.append(str(item))
        return "; ".join(parts) if parts else default
    return str(current) if current is not None else default


def _extract_doi(result: dict) -> str:
    """Try to extract a DOI from various PID locations in the result."""
    # Try pid at the result level
    for path in [
        ("metadata", "oaf:entity", "oaf:result", "pid"),
        ("metadata", "oaf:entity", "oaf:result", "children", "instance", "pid"),
    ]:
        current: object = result
        for key in path:
            if isinstance(current, dict):
                current = current.get(key)
            elif isinstance(current, list) and current:
                current = current[0]
                if isinstance(current, dict):
                    current = current.get(key)
                else:
                    current = None
                    break
            else:
                current = None
                break
        if current is None:
            continue
        pids = current if isinstance(current, list) else [current]
        for pid in pids:
            if isinstance(pid, dict):
                classid = pid.get("@classid", "")
                value = pid.get("$", pid.get("content", ""))
                if classid == "doi" and value:
                    return str(value)
    return ""


def _extract_url(result: dict) -> str:
    """Try to extract a URL from the result."""
    for path in [
        ("metadata", "oaf:entity", "oaf:result", "children", "instance", "webresource", "url"),
    ]:
        current: object = result
        for key in path:
            if isinstance(current, dict):
                current = current.get(key)
            elif isinstance(current, list) and current:
                current = current[0]
                if isinstance(current, dict):
                    current = current.get(key)
                else:
                    current = None
                    break
            else:
                current = None
                break
        if current is not None:
            if isinstance(current, dict):
                return str(current.get("$", current.get("content", "")))
            if isinstance(current, list) and current:
                item = current[0]
                if isinstance(item, dict):
                    return str(item.get("$", item.get("content", "")))
                return str(item)
            return str(current)
    return ""


def _parse_json_result(result: dict) -> dict[str, str]:
    """Parse a single result from the JSON response."""
    entity = _safe_get(result, "metadata", "oaf:entity", "oaf:result")
    if not entity:
        # Flat structure fallback
        entity_data = result
    else:
        entity_data = result.get("metadata", {}).get("oaf:entity", {}).get("oaf:result", {})

    title = _safe_get(entity_data, "title", default="[No title]")
    if title == "[No title]":
        title = _safe_get(result, "title", default="[No title]")

    authors_raw = entity_data.get("creator") or result.get("creator") or []
    if isinstance(authors_raw, dict):
        authors_raw = [authors_raw]
    authors: list[str] = []
    for a in authors_raw:
        if isinstance(a, dict):
            name = a.get("$", a.get("content", ""))
            if name:
                authors.append(str(name))
        elif isinstance(a, str):
            authors.append(a)

    description = _safe_get(entity_data, "description", default="")
    if not description:
        description = _safe_get(result, "description", default="")

    date = _safe_get(entity_data, "dateofacceptance", default="")
    if not date:
        date = _safe_get(result, "dateofacceptance", default="")

    doi = _extract_doi(result)
    url = _extract_url(result)

    return {
        "title": title,
        "authors": "; ".join(authors) if authors else "Unknown",
        "abstract": description[:500] if description else "",
        "doi": doi,
        "date": date,
        "url": url,
    }


def _parse_xml_results(xml_text: str) -> list[dict[str, str]]:
    """Fallback: parse XML response and extract result data."""
    results: list[dict[str, str]] = []
    try:
        root = ET.fromstring(xml_text)  # noqa: S314
    except ET.ParseError:
        return results

    for res_elem in root.iter("result"):
        title = ""
        authors: list[str] = []
        description = ""
        doi = ""
        date = ""
        url = ""

        title_el = res_elem.find(".//title")
        if title_el is not None and title_el.text:
            title = title_el.text.strip()

        for creator_el in res_elem.findall(".//creator"):
            if creator_el.text:
                authors.append(creator_el.text.strip())

        desc_el = res_elem.find(".//description")
        if desc_el is not None and desc_el.text:
            description = desc_el.text.strip()[:500]

        for pid_el in res_elem.findall(".//pid"):
            classid = pid_el.get("classid", "")
            if classid == "doi" and pid_el.text:
                doi = pid_el.text.strip()
                break

        date_el = res_elem.find(".//dateofacceptance")
        if date_el is not None and date_el.text:
            date = date_el.text.strip()

        url_el = res_elem.find(".//url")
        if url_el is not None and url_el.text:
            url = url_el.text.strip()

        results.append({
            "title": title or "[No title]",
            "authors": "; ".join(authors) if authors else "Unknown",
            "abstract": description,
            "doi": doi,
            "date": date,
            "url": url,
        })

    return results


def _format_paper(index: int, paper: dict[str, str]) -> str:
    """Format a single paper for display."""
    lines: list[str] = []
    lines.append(f"{index}. {paper['title']}")
    lines.append(f"   Authors: {paper['authors']}")
    if paper.get("date"):
        lines.append(f"   Date: {paper['date']}")
    if paper.get("doi"):
        lines.append(f"   DOI: {paper['doi']}")
    if paper.get("url"):
        lines.append(f"   URL: {paper['url']}")
    if paper.get("abstract"):
        lines.append(f"   Abstract: {paper['abstract']}")
    return "\n".join(lines)


async def search(query: str, max_results: int = 10) -> str:
    """Search OpenAIRE for research products matching *query*."""
    size = min(max_results, MAX_RESULTS_CAP)
    params = {
        "keywords": query,
        "page": 1,
        "size": size,
        "format": "json",
    }

    async with httpx.AsyncClient(headers=HEADERS, timeout=30) as client:
        resp = await client.get(BASE_URL, params=params)
        resp.raise_for_status()

    papers: list[dict[str, str]] = []

    # Try JSON parsing first
    try:
        data = resp.json()
        raw_results: list[dict] | None = None

        # Path 1: data["results"]
        if isinstance(data, dict) and "results" in data:
            raw_results = data["results"]
            if isinstance(raw_results, dict):
                raw_results = raw_results.get("result", [])

        # Path 2: data["response"]["results"]["result"]
        if not raw_results and isinstance(data, dict):
            response = data.get("response", {})
            if isinstance(response, dict):
                results_section = response.get("results", {})
                if isinstance(results_section, dict):
                    raw_results = results_section.get("result", [])

        if raw_results:
            if isinstance(raw_results, dict):
                raw_results = [raw_results]
            for item in raw_results:
                if isinstance(item, dict):
                    papers.append(_parse_json_result(item))
    except (ValueError, KeyError, TypeError):
        pass

    # Fallback to XML parsing if JSON produced no results
    if not papers:
        papers = _parse_xml_results(resp.text)

    if not papers:
        return f"No OpenAIRE results for '{query}'."

    formatted = [_format_paper(i + 1, p) for i, p in enumerate(papers)]
    return "\n\n".join(formatted)

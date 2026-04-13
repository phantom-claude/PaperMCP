"""HuggingFace Daily Papers source — trending papers from HuggingFace."""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional

import httpx

logger = logging.getLogger("paper_mcp.huggingface")

HF_API = "https://huggingface.co/api"


async def _fetch_daily_papers(date: str) -> list[dict]:
    """Fetch papers from HuggingFace daily papers API."""
    url = f"{HF_API}/daily_papers?date={date}"
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"Failed to fetch HF papers for {date}: {e}")
            return []

    papers = []
    for item in data:
        paper = item.get("paper", {})
        authors = [a.get("name", "") for a in paper.get("authors", []) if not a.get("hidden")]
        papers.append({
            "title": item.get("title", paper.get("title", "Untitled")),
            "authors": authors,
            "abstract": paper.get("summary", ""),
            "arxiv_id": paper.get("id", ""),
            "url": f"https://huggingface.co/papers/{paper.get('id', '')}",
            "pdf_url": f"https://arxiv.org/pdf/{paper.get('id', '')}.pdf" if paper.get("id") else "",
            "votes": item.get("paper", {}).get("upvotes", 0),
            "submitted_by": item.get("submittedBy", {}).get("fullname", ""),
        })

    return papers


async def _fetch_paper_detail(arxiv_id: str) -> Optional[dict]:
    """Fetch a single paper's details from HuggingFace API."""
    url = f"{HF_API}/papers/{arxiv_id}"
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return None
            data = resp.json()
        except Exception:
            return None

    authors = [a.get("name", "") for a in data.get("authors", []) if not a.get("hidden")]
    return {
        "title": data.get("title", "Untitled"),
        "authors": authors,
        "abstract": data.get("summary", ""),
        "arxiv_id": data.get("id", ""),
        "url": f"https://huggingface.co/papers/{data.get('id', '')}",
        "pdf_url": f"https://arxiv.org/pdf/{data.get('id', '')}.pdf" if data.get("id") else "",
        "upvotes": data.get("upvotes", 0),
    }


async def get_daily_papers(date: Optional[str] = None) -> str:
    """Get HuggingFace daily papers for a given date (YYYY-MM-DD). Defaults to today."""
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    papers = await _fetch_daily_papers(date)

    if not papers:
        return f"No papers found for {date}."

    lines = [f"HuggingFace Daily Papers for {date} — {len(papers)} papers:\n"]
    for p in papers:
        lines.append(f"**{p['title']}**")
        if p["authors"]:
            lines.append(f"  Authors: {', '.join(p['authors'][:5])}")
        if p["abstract"]:
            lines.append(f"  Abstract: {p['abstract'][:200]}...")
        lines.append(f"  URL: {p['url']}")
        if p["pdf_url"]:
            lines.append(f"  PDF: {p['pdf_url']}")
        lines.append(f"  Votes: {p['votes']}")
        lines.append("")

    return "\n".join(lines)


async def get_paper(arxiv_id: str) -> str:
    """Get a specific paper's details from HuggingFace by ArXiv ID."""
    paper = await _fetch_paper_detail(arxiv_id)
    if not paper:
        return f"Paper '{arxiv_id}' not found on HuggingFace."

    lines = [f"**{paper['title']}**"]
    if paper["authors"]:
        lines.append(f"  Authors: {', '.join(paper['authors'])}")
    if paper["abstract"]:
        lines.append(f"  Abstract: {paper['abstract']}")
    lines.append(f"  URL: {paper['url']}")
    if paper["pdf_url"]:
        lines.append(f"  PDF: {paper['pdf_url']}")
    lines.append(f"  Upvotes: {paper['upvotes']}")
    return "\n".join(lines)

"""ArXiv paper source — search, download, and read papers from arXiv."""

import logging
import os
import re
import asyncio
from pathlib import Path
from typing import Optional

import arxiv
import httpx

logger = logging.getLogger("paper_mcp.arxiv")

STORAGE_PATH = Path(os.environ.get("PAPER_MCP_STORAGE", "~/.paper-mcp/papers")).expanduser()


def _ensure_storage():
    STORAGE_PATH.mkdir(parents=True, exist_ok=True)


async def search_papers(
    query: str,
    max_results: int = 10,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    categories: Optional[list[str]] = None,
) -> str:
    """Search arXiv for papers matching query with optional filters."""
    from datetime import datetime

    def _search():
        search_query = query
        if categories:
            cat_filter = " OR ".join(f"cat:{c}" for c in categories)
            search_query = f"({query}) AND ({cat_filter})"

        client = arxiv.Client()
        search = arxiv.Search(
            query=search_query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
        )

        results = []
        for paper in client.results(search):
            pub_date = paper.published

            if date_from:
                from_dt = datetime.strptime(date_from, "%Y-%m-%d")
                if pub_date.replace(tzinfo=None) < from_dt:
                    continue
            if date_to:
                to_dt = datetime.strptime(date_to, "%Y-%m-%d")
                if pub_date.replace(tzinfo=None) > to_dt:
                    continue

            results.append({
                "id": paper.entry_id.split("/abs/")[-1],
                "title": paper.title,
                "authors": [a.name for a in paper.authors],
                "abstract": paper.summary,
                "published": pub_date.strftime("%Y-%m-%d"),
                "categories": paper.categories,
                "pdf_url": paper.pdf_url,
                "url": paper.entry_id,
            })

        return results

    results = await asyncio.to_thread(_search)

    if not results:
        return "No papers found matching your query."

    lines = [f"Found {len(results)} papers:\n"]
    for p in results:
        lines.append(f"**{p['title']}**")
        lines.append(f"  ID: {p['id']}")
        lines.append(f"  Authors: {', '.join(p['authors'][:5])}")
        lines.append(f"  Published: {p['published']}")
        lines.append(f"  Categories: {', '.join(p['categories'])}")
        lines.append(f"  Abstract: {p['abstract'][:200]}...")
        lines.append(f"  URL: {p['url']}")
        lines.append("")

    return "\n".join(lines)


async def download_paper(paper_id: str) -> str:
    """Download a paper PDF from arXiv by its ID."""
    _ensure_storage()

    clean_id = paper_id.replace("arxiv:", "").strip()
    pdf_path = STORAGE_PATH / f"{clean_id.replace('/', '_')}.pdf"

    if pdf_path.exists():
        return f"Paper {clean_id} already downloaded at {pdf_path}"

    pdf_url = f"https://arxiv.org/pdf/{clean_id}.pdf"

    async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
        response = await client.get(pdf_url)
        response.raise_for_status()
        pdf_path.write_bytes(response.content)

    return f"Downloaded paper {clean_id} to {pdf_path} ({len(response.content)} bytes)"


async def list_papers() -> str:
    """List all downloaded papers in local storage."""
    _ensure_storage()

    pdf_files = list(STORAGE_PATH.glob("*.pdf"))
    if not pdf_files:
        return "No papers downloaded yet."

    lines = [f"Downloaded papers ({len(pdf_files)}):\n"]
    for f in sorted(pdf_files):
        paper_id = f.stem.replace("_", "/")
        size_mb = f.stat().st_size / (1024 * 1024)
        lines.append(f"  - {paper_id} ({size_mb:.1f} MB)")

    return "\n".join(lines)


async def read_paper(paper_id: str) -> str:
    """Read the content of a downloaded arXiv paper."""
    _ensure_storage()

    clean_id = paper_id.replace("arxiv:", "").strip()
    pdf_path = STORAGE_PATH / f"{clean_id.replace('/', '_')}.pdf"

    if not pdf_path.exists():
        return f"Paper {clean_id} not found. Download it first with arxiv_download."

    try:
        import pymupdf4llm
        text = await asyncio.to_thread(pymupdf4llm.to_markdown, str(pdf_path))
        return text
    except ImportError:
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(str(pdf_path))
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
            return text if text.strip() else "Could not extract text from PDF."
        except Exception as e:
            return f"Error reading paper: {e}"

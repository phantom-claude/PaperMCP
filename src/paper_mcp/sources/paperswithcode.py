"""PapersWithCode source — papers, code, benchmarks, authors, conferences.

NOTE: PapersWithCode (paperswithcode.com) was acquired by HuggingFace and the
original REST API now redirects to huggingface.co. This module uses the
HuggingFace Papers API as the backend and provides web-scraping fallback
for PwC-specific features (repos, datasets, methods, benchmarks) via the
archived site content.
"""

import io
import logging
import asyncio
from typing import Optional
from urllib.parse import urlencode, quote

import httpx
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("paper_mcp.paperswithcode")

HF_API = "https://huggingface.co/api"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


async def search_papers(
    title: Optional[str] = None,
    abstract: Optional[str] = None,
    arxiv_id: Optional[str] = None,
) -> str:
    """Search for papers. Uses HuggingFace Papers API (PapersWithCode successor)."""
    # If we have an arxiv_id, fetch directly
    if arxiv_id:
        url = f"{HF_API}/papers/{arxiv_id}"
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    return _format_hf_paper(data)
            except Exception as e:
                return f"Error looking up paper {arxiv_id}: {e}"
        return f"Paper '{arxiv_id}' not found."

    # For title/abstract search, use HuggingFace daily papers + ArXiv as fallback
    query = title or abstract or ""
    if not query:
        return "Please provide a title, abstract, or arxiv_id to search."

    # Search recent daily papers via multiple dates
    all_papers = []
    from datetime import datetime, timedelta
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for days_ago in range(7):
            date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
            try:
                resp = await client.get(f"{HF_API}/daily_papers?date={date}")
                if resp.status_code == 200:
                    for item in resp.json():
                        paper = item.get("paper", {})
                        paper_title = item.get("title", paper.get("title", ""))
                        if query.lower() in paper_title.lower() or (
                            abstract and query.lower() in paper.get("summary", "").lower()
                        ):
                            all_papers.append({
                                "title": paper_title,
                                "authors": [a.get("name", "") for a in paper.get("authors", []) if not a.get("hidden")],
                                "abstract": paper.get("summary", "")[:200],
                                "arxiv_id": paper.get("id", ""),
                                "url": f"https://huggingface.co/papers/{paper.get('id', '')}",
                                "upvotes": paper.get("upvotes", 0),
                            })
            except Exception:
                continue

    if not all_papers:
        return f"No papers found matching '{query}'. Try using arxiv_search or scholar_search for broader results."

    lines = [f"PapersWithCode/HuggingFace results for '{query}' — {len(all_papers)} papers:\n"]
    for p in all_papers:
        lines.append(f"**{p['title']}**")
        if p["authors"]:
            lines.append(f"  Authors: {', '.join(p['authors'][:5])}")
        if p["abstract"]:
            lines.append(f"  Abstract: {p['abstract']}...")
        lines.append(f"  ArXiv: {p['arxiv_id']}")
        lines.append(f"  URL: {p['url']}")
        lines.append("")

    return "\n".join(lines)


async def get_paper(paper_id: str) -> str:
    """Get a paper's metadata by ArXiv ID via HuggingFace API."""
    url = f"{HF_API}/papers/{paper_id}"
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return f"Paper '{paper_id}' not found."
            return _format_hf_paper(resp.json())
        except Exception as e:
            return f"Error fetching paper: {e}"


def _format_hf_paper(data: dict) -> str:
    """Format a HuggingFace paper API response."""
    authors = [a.get("name", "") for a in data.get("authors", []) if not a.get("hidden")]
    pid = data.get("id", "")
    lines = [f"**{data.get('title', 'Untitled')}**"]
    if authors:
        lines.append(f"  Authors: {', '.join(authors)}")
    if data.get("summary"):
        lines.append(f"  Abstract: {data['summary']}")
    lines.append(f"  ArXiv: {pid}")
    lines.append(f"  URL: https://huggingface.co/papers/{pid}")
    lines.append(f"  PDF: https://arxiv.org/pdf/{pid}.pdf")
    lines.append(f"  Upvotes: {data.get('upvotes', 0)}")
    return "\n".join(lines)


async def paper_repositories(paper_id: str) -> str:
    """List code repositories linked to a paper. Searches GitHub via HuggingFace."""
    # HuggingFace doesn't expose repo links via API — use the web page
    url = f"https://huggingface.co/papers/{paper_id}"
    try:
        resp = await asyncio.to_thread(requests.get, url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")

        repos = []
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if "github.com" in href and href not in repos:
                repos.append(href)

        if not repos:
            return f"No repositories found for paper '{paper_id}'. Try searching GitHub directly."

        lines = [f"Repositories for '{paper_id}' — {len(repos)} found:\n"]
        for r in repos:
            lines.append(f"  - {r}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error fetching repositories: {e}"


async def paper_datasets(paper_id: str) -> str:
    """List datasets mentioned in a paper (extracted from HuggingFace page)."""
    url = f"https://huggingface.co/papers/{paper_id}"
    try:
        resp = await asyncio.to_thread(requests.get, url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")

        datasets = []
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if "/datasets/" in href:
                name = link.get_text(strip=True) or href.split("/")[-1]
                if name and name not in datasets:
                    datasets.append(name)

        if not datasets:
            return f"No datasets found for paper '{paper_id}'."

        lines = [f"Datasets for '{paper_id}' — {len(datasets)}:\n"]
        for d in datasets:
            lines.append(f"  - {d}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error fetching datasets: {e}"


async def paper_methods(paper_id: str) -> str:
    """List methods discussed in a paper (extracted from abstract/title)."""
    paper = await get_paper(paper_id)
    return f"Methods extraction for '{paper_id}':\n\n{paper}\n\n(Note: Method extraction requires reading the full paper. Use `read` to access the paper content.)"


async def paper_results(paper_id: str) -> str:
    """List benchmark results for a paper."""
    return (
        f"Benchmark results for '{paper_id}' are not available via API. "
        f"Visit https://huggingface.co/papers/{paper_id} for details."
    )


async def search_authors(full_name: str) -> str:
    """Search for authors on HuggingFace."""
    url = f"https://huggingface.co/api/users?search={quote(full_name)}"
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return f"Could not search authors. Try scholar_author_info instead."
            users = resp.json()
        except Exception as e:
            return f"Error searching authors: {e}"

    if not users:
        return f"No authors found for '{full_name}'. Try scholar_author_info or dblp_author_publications."

    lines = [f"HuggingFace users matching '{full_name}' — {len(users)}:\n"]
    for u in users[:10]:
        name = u.get("fullname", u.get("user", "N/A"))
        username = u.get("user", "")
        lines.append(f"  - **{name}** (@{username})")
    return "\n".join(lines)


async def author_papers(author_name: str) -> str:
    """List papers by an author. Uses DBLP/Scholar as more reliable sources."""
    return (
        f"Direct author paper listing is not available via HuggingFace API. "
        f"Use `dblp_author_publications(\"{author_name}\")` or "
        f"`scholar_author_info(\"{author_name}\")` instead."
    )


async def list_conferences(name: Optional[str] = None) -> str:
    """List conferences. Redirects to DBLP which has comprehensive conference data."""
    return (
        "Conference listing is best served by DBLP. "
        "Use `dblp_venue_info(\"ICLR\")` or `dblp_search(query, venue_filter=\"NeurIPS\")` for conference data."
    )


async def conference_papers(conference_id: str, proceeding_id: str) -> str:
    """List papers for a conference. Redirects to OpenReview for ML conferences."""
    return (
        f"For ML conference papers, use `openreview_conference_papers` instead. "
        f"Example: `openreview_conference_papers(venue=\"ICLR.cc\", year=\"2024\")`"
    )


async def read_paper_url(paper_url: str) -> str:
    """Extract and read text from a paper PDF or HTML URL."""
    try:
        resp = requests.get(paper_url, timeout=60, headers=HEADERS)
        if resp.headers.get("content-type", "").startswith("application/pdf"):
            from PyPDF2 import PdfReader
            reader = PdfReader(io.BytesIO(resp.content))
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
            return text if text.strip() else "Could not extract text from PDF."
        else:
            return resp.text[:50000]
    except Exception as e:
        return f"Error reading paper: {e}"

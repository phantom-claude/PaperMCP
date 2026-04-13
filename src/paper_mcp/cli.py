#!/usr/bin/env python3
"""CLI interface for paper-search — search, download, and read academic papers.

Provides a command-line tool that wraps all 25+ academic paper sources
for quick terminal-based paper discovery.

Usage:
    paper-search search "machine learning" -n 5
    paper-search search "transformers" -s arxiv,semantic,crossref
    paper-search download arxiv 2401.12345
    paper-search read arxiv 2401.12345
    paper-search sources
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any, Dict, List

from .sources.google_scholar import GoogleScholarSearcher
from .sources.iacr import IACRSearcher
from .sources.core import CORESearcher
from .sources.citeseerx import CiteSeerXSearcher
from .sources.ssrn import SSRNSearcher
from .sources.base_search import BASESearcher
from .sources.medrxiv import MedRxivSearcher
from .sources.sci_hub import SciHubFetcher

# Lazy-init registry of class-based searchers
SEARCHERS: Dict[str, Any] = {}


def _init_searchers() -> None:
    """Lazily initialize class-based searcher instances."""
    if SEARCHERS:
        return

    SEARCHERS["google_scholar"] = GoogleScholarSearcher()
    SEARCHERS["iacr"] = IACRSearcher()
    SEARCHERS["core"] = CORESearcher()
    SEARCHERS["citeseerx"] = CiteSeerXSearcher()
    SEARCHERS["ssrn"] = SSRNSearcher()
    SEARCHERS["base"] = BASESearcher()
    SEARCHERS["medrxiv"] = MedRxivSearcher()

    # Optional paid connectors
    try:
        from .config import get_env
        ieee_key = get_env("IEEE_API_KEY", "")
        if ieee_key:
            from .sources.ieee import IEEESearcher
            SEARCHERS["ieee"] = IEEESearcher()
        acm_key = get_env("ACM_API_KEY", "")
        if acm_key:
            from .sources.acm import ACMSearcher
            SEARCHERS["acm"] = ACMSearcher()
    except Exception:
        pass


# Sources handled by the async unified module
ASYNC_SOURCES = [
    "arxiv", "dblp", "scholar", "pwc", "hf",
    "ss", "crossref", "openalex",
    "pubmed", "biorxiv", "europepmc",
    "hal", "pmc", "doaj", "zenodo", "openaire", "inspirehep",
    "chemrxiv",
]

ALL_SOURCES = ASYNC_SOURCES + [
    "google_scholar", "iacr", "core", "citeseerx",
    "ssrn", "base", "medrxiv",
]


def _parse_sources(sources: str) -> List[str]:
    if not sources or sources.strip().lower() == "all":
        return ALL_SOURCES
    return [p.strip().lower() for p in sources.split(",") if p.strip()]


def _paper_unique_key(paper: Dict[str, Any]) -> str:
    doi = (paper.get("doi") or "").strip().lower()
    if doi:
        return f"doi:{doi}"
    title = (paper.get("title") or "").strip().lower()
    authors = (paper.get("authors") or "").strip().lower()
    if title:
        return f"title:{title}|authors:{authors}"
    return f"id:{(paper.get('paper_id') or '').strip().lower()}"


def _dedupe(papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: set[str] = set()
    out: list[Dict[str, Any]] = []
    for p in papers:
        k = _paper_unique_key(p)
        if k not in seen:
            seen.add(k)
            out.append(p)
    return out


async def _async_search_class(searcher: Any, query: str, max_results: int) -> List[Dict]:
    papers = await asyncio.to_thread(searcher.search, query, max_results=max_results)
    return [p.to_dict() for p in papers]


async def cmd_search(args: argparse.Namespace) -> int:
    _init_searchers()
    selected = _parse_sources(args.sources)

    tasks = {}

    # Handle async sources via unified module
    async_selected = [s for s in selected if s in ASYNC_SOURCES]
    if async_selected:
        from .sources import unified
        async def _unified_search():
            raw = await unified.search(args.query, ",".join(async_selected), args.max_results)
            return raw
        tasks["_unified"] = _unified_search()

    # Handle class-based sources
    class_selected = [s for s in selected if s in SEARCHERS]
    for src in class_selected:
        tasks[src] = _async_search_class(SEARCHERS[src], args.query, args.max_results)

    if not tasks:
        print(json.dumps({"error": "No valid sources selected", "available": ALL_SOURCES}))
        return 1

    names = list(tasks.keys())
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)

    merged: List[Dict[str, Any]] = []
    errors: Dict[str, str] = {}

    for name, result in zip(names, results):
        if isinstance(result, Exception):
            errors[name] = str(result)
        elif isinstance(result, str):
            # unified search returns a string
            print(result)
        elif isinstance(result, list):
            for p in result:
                if not p.get("source"):
                    p["source"] = name
                merged.append(p)

    if merged:
        deduped = _dedupe(merged)
        output = {
            "sources_used": class_selected,
            "errors": errors,
            "total": len(deduped),
            "papers": deduped,
        }
        print(json.dumps(output, indent=2, default=str))

    return 0


async def cmd_download(args: argparse.Namespace) -> int:
    _init_searchers()
    source = args.source.strip().lower()

    if source in SEARCHERS:
        try:
            result = await asyncio.to_thread(SEARCHERS[source].download_pdf, args.paper_id, args.save_path)
            print(json.dumps({"status": "ok", "path": result}))
            return 0
        except Exception as e:
            print(json.dumps({"status": "error", "message": str(e)}))
            return 1
    elif source == "scihub":
        fetcher = SciHubFetcher(output_dir=args.save_path)
        result = await asyncio.to_thread(fetcher.download_pdf, args.paper_id)
        if result:
            print(json.dumps({"status": "ok", "path": result}))
            return 0
        print(json.dumps({"status": "error", "message": "Sci-Hub download failed"}))
        return 1
    else:
        # Try unified download
        from .sources import unified
        result = await unified.download(args.paper_id)
        print(result)
        return 0


async def cmd_read(args: argparse.Namespace) -> int:
    _init_searchers()
    source = args.source.strip().lower()

    if source in SEARCHERS:
        try:
            text = await asyncio.to_thread(SEARCHERS[source].read_paper, args.paper_id, args.save_path)
            print(text)
            return 0
        except Exception as e:
            print(json.dumps({"status": "error", "message": str(e)}))
            return 1
    else:
        from .sources import unified
        result = await unified.read(args.paper_id)
        print(result)
        return 0


async def cmd_sources(_args: argparse.Namespace) -> int:
    _init_searchers()
    all_avail = sorted(set(ALL_SOURCES) | set(SEARCHERS.keys()))
    print(json.dumps({"sources": all_avail}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="paper-search",
        description="Search, download, and read academic papers from 30+ sources.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_search = sub.add_parser("search", help="Search for papers across academic platforms")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument("-n", "--max-results", type=int, default=5)
    p_search.add_argument("-s", "--sources", default="all",
                          help="Comma-separated sources or 'all' (default: all)")

    p_dl = sub.add_parser("download", help="Download a paper PDF")
    p_dl.add_argument("source", help="Source platform (e.g. arxiv, scihub)")
    p_dl.add_argument("paper_id", help="Paper identifier")
    p_dl.add_argument("-o", "--save-path", default="./downloads")

    p_read = sub.add_parser("read", help="Download and extract text from a paper")
    p_read.add_argument("source", help="Source platform")
    p_read.add_argument("paper_id", help="Paper identifier")
    p_read.add_argument("-o", "--save-path", default="./downloads")

    sub.add_parser("sources", help="List available sources")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "search": cmd_search,
        "download": cmd_download,
        "read": cmd_read,
        "sources": cmd_sources,
    }

    exit_code = asyncio.run(dispatch[args.command](args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

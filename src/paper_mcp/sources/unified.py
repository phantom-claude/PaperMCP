"""
Unified paper tools — search, download, read, list across all sources.

Provides 4 high-level tools that fan out to multiple backends in parallel
and merge results into a single response.  Combines 30+ academic paper
sources.
"""

import asyncio
import logging
import re
from typing import Optional

from . import arxiv, dblp, huggingface, paperswithcode, scholar
from . import semanticscholar, crossref, openalex
from . import pubmed, biorxiv, europepmc
from . import hal, pmc, doaj, zenodo, openaire, unpaywall, inspirehep
from . import chemrxiv

logger = logging.getLogger("paper_mcp.unified")

ALL_SEARCH_SOURCES = [
    "arxiv", "dblp", "scholar", "pwc", "hf",
    "ss", "crossref", "openalex",
    "pubmed", "biorxiv", "europepmc",
    "hal", "pmc", "doaj", "zenodo", "openaire", "inspirehep",
    "google_scholar", "iacr", "core", "citeseerx",
    "ssrn", "base", "medrxiv", "chemrxiv",
]
ALL_DOWNLOAD_SOURCES = ["arxiv"]

SOURCE_ALIASES = {
    "arxiv": "arxiv",
    "dblp": "dblp",
    "scholar": "scholar", "google": "scholar", "google_scholar": "google_scholar",
    "pwc": "pwc", "paperswithcode": "pwc", "papers_with_code": "pwc",
    "hf": "hf", "huggingface": "hf", "hugging_face": "hf",
    "ss": "ss", "semanticscholar": "ss", "semantic_scholar": "ss", "s2": "ss",
    "crossref": "crossref", "cr": "crossref",
    "openalex": "openalex", "oa": "openalex", "open_alex": "openalex",
    "pubmed": "pubmed", "pm": "pubmed",
    "biorxiv": "biorxiv",
    "europepmc": "europepmc", "epmc": "europepmc", "europe_pmc": "europepmc",
    "hal": "hal",
    "pmc": "pmc", "pubmedcentral": "pmc",
    "doaj": "doaj",
    "zenodo": "zenodo",
    "openaire": "openaire",
    "unpaywall": "unpaywall",
    "inspirehep": "inspirehep", "inspire": "inspirehep",
    "iacr": "iacr",
    "core": "core",
    "citeseerx": "citeseerx",
    "ssrn": "ssrn",
    "base": "base",
    "medrxiv": "medrxiv",
    "chemrxiv": "chemrxiv",
}


def _parse_sources(sources: Optional[str]) -> list[str]:
    """Parse a comma-separated source list, or return all sources."""
    if not sources:
        return ALL_SEARCH_SOURCES
    parsed = [s.strip().lower() for s in sources.split(",") if s.strip()]
    valid = []
    for s in parsed:
        normalized = SOURCE_ALIASES.get(s)
        if normalized:
            valid.append(normalized)
        else:
            logger.warning(f"Unknown source: {s}")
    return valid or ALL_SEARCH_SOURCES


def _detect_source(paper_id: str) -> tuple[str, str]:
    """
    Auto-detect which source a paper ID or URL belongs to.
    Returns (source_name, cleaned_id).
    """
    pid = paper_id.strip()

    # ArXiv: 2401.12345, arxiv:2401.12345, https://arxiv.org/abs/2401.12345
    if re.match(r"^\d{4}\.\d{4,5}(v\d+)?$", pid):
        return "arxiv", pid
    if pid.lower().startswith("arxiv:"):
        return "arxiv", pid[6:]
    m = re.search(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})", pid)
    if m:
        return "arxiv", m.group(1)

    # OpenReview: https://openreview.net/forum?id=XXX
    m = re.search(r"openreview\.net/(?:forum|pdf)\?id=([A-Za-z0-9_-]+)", pid)
    if m:
        return "openreview", m.group(1)

    # DBLP key: conf/nips/VaswaniSPUJGKP17 or journals/jmlr/...
    if re.match(r"^(conf|journals|series|books|phd)/", pid):
        return "dblp", pid

    # PapersWithCode: typically slug-style IDs
    if re.match(r"^[a-z0-9]+-[a-z0-9-]+$", pid):
        return "pwc", pid

    # URL-based detection
    if "paperswithcode.com" in pid:
        return "pwc_url", pid
    if "huggingface.co/papers" in pid:
        return "hf_url", pid
    if "dblp.org" in pid:
        return "dblp_url", pid

    # Semantic Scholar paper ID (40-char hex)
    if re.match(r"^[0-9a-f]{40}$", pid):
        return "ss", pid

    # DOI format: 10.xxxx/...
    m = re.match(r"^(10\.\d{4,9}/[^\s]+)$", pid)
    if m:
        return "doi", m.group(1)
    # doi.org URL
    m = re.search(r"doi\.org/(10\.\d{4,9}/[^\s]+)", pid)
    if m:
        return "doi", m.group(1)

    # Semantic Scholar URL
    m = re.search(r"semanticscholar\.org/paper/[^/]*/([0-9a-f]{40})", pid)
    if m:
        return "ss", m.group(1)

    # If it looks like a URL, try reading it directly
    if pid.startswith("http://") or pid.startswith("https://"):
        return "url", pid

    # Default: try arXiv
    return "arxiv", pid


async def _search_arxiv(query: str, max_results: int) -> list[dict]:
    """Search ArXiv and return normalized results."""
    try:
        raw = await arxiv.search_papers(query, max_results)
        if raw.startswith("No papers"):
            return []
        return [{"source": "arxiv", "text": raw}]
    except Exception as e:
        logger.error(f"ArXiv search failed: {e}")
        return [{"source": "arxiv", "text": f"[ArXiv error: {e}]"}]


async def _search_dblp(query: str, max_results: int) -> list[dict]:
    """Search DBLP and return normalized results."""
    try:
        raw = await dblp.search(query, max_results)
        if raw.startswith("No DBLP"):
            return []
        return [{"source": "dblp", "text": raw}]
    except Exception as e:
        logger.error(f"DBLP search failed: {e}")
        return [{"source": "dblp", "text": f"[DBLP error: {e}]"}]


async def _search_scholar(query: str, max_results: int) -> list[dict]:
    """Search Google Scholar and return normalized results."""
    try:
        raw = await scholar.search(query, max_results)
        if raw.startswith("No results"):
            return []
        return [{"source": "scholar", "text": raw}]
    except Exception as e:
        logger.error(f"Scholar search failed: {e}")
        return [{"source": "scholar", "text": f"[Scholar error: {e}]"}]


async def _search_pwc(query: str, max_results: int) -> list[dict]:
    """Search PapersWithCode and return normalized results."""
    try:
        raw = await paperswithcode.search_papers(title=query)
        if raw.startswith("No papers"):
            return []
        return [{"source": "pwc", "text": raw}]
    except Exception as e:
        logger.error(f"PapersWithCode search failed: {e}")
        return [{"source": "pwc", "text": f"[PapersWithCode error: {e}]"}]


async def _search_hf(query: str, max_results: int) -> list[dict]:
    """Get HuggingFace daily papers (not keyword-searchable, returns today's papers)."""
    try:
        raw = await huggingface.get_daily_papers()
        if raw.startswith("No papers"):
            return []
        return [{"source": "hf", "text": raw}]
    except Exception as e:
        logger.error(f"HuggingFace search failed: {e}")
        return [{"source": "hf", "text": f"[HuggingFace error: {e}]"}]


async def _search_ss(query: str, max_results: int) -> list[dict]:
    """Search Semantic Scholar and return normalized results."""
    try:
        raw = await semanticscholar.search(query, max_results)
        if raw.startswith("No Semantic"):
            return []
        return [{"source": "ss", "text": raw}]
    except Exception as e:
        logger.error(f"Semantic Scholar search failed: {e}")
        return [{"source": "ss", "text": f"[Semantic Scholar error: {e}]"}]


async def _search_crossref(query: str, max_results: int) -> list[dict]:
    """Search CrossRef and return normalized results."""
    try:
        raw = await crossref.search(query, max_results)
        if raw.startswith("No CrossRef"):
            return []
        return [{"source": "crossref", "text": raw}]
    except Exception as e:
        logger.error(f"CrossRef search failed: {e}")
        return [{"source": "crossref", "text": f"[CrossRef error: {e}]"}]


async def _search_openalex(query: str, max_results: int) -> list[dict]:
    """Search OpenAlex and return normalized results."""
    try:
        raw = await openalex.search(query, max_results)
        if raw.startswith("No OpenAlex"):
            return []
        return [{"source": "openalex", "text": raw}]
    except Exception as e:
        logger.error(f"OpenAlex search failed: {e}")
        return [{"source": "openalex", "text": f"[OpenAlex error: {e}]"}]


async def _search_pubmed(query: str, max_results: int) -> list[dict]:
    """Search PubMed and return normalized results."""
    try:
        raw = await pubmed.search(query, max_results)
        if raw.startswith("No PubMed"):
            return []
        return [{"source": "pubmed", "text": raw}]
    except Exception as e:
        logger.error(f"PubMed search failed: {e}")
        return [{"source": "pubmed", "text": f"[PubMed error: {e}]"}]


async def _search_biorxiv(query: str, max_results: int) -> list[dict]:
    """Search bioRxiv and return normalized results."""
    try:
        raw = await biorxiv.search(query, max_results)
        if raw.startswith("No ") and "results" in raw:
            return []
        return [{"source": "biorxiv", "text": raw}]
    except Exception as e:
        logger.error(f"bioRxiv search failed: {e}")
        return [{"source": "biorxiv", "text": f"[bioRxiv error: {e}]"}]


async def _search_europepmc(query: str, max_results: int) -> list[dict]:
    """Search Europe PMC and return normalized results."""
    try:
        raw = await europepmc.search(query, max_results)
        if raw.startswith("No Europe PMC"):
            return []
        return [{"source": "europepmc", "text": raw}]
    except Exception as e:
        logger.error(f"Europe PMC search failed: {e}")
        return [{"source": "europepmc", "text": f"[Europe PMC error: {e}]"}]


# ─── Additional source wrappers (functional async modules) ────────────


async def _search_hal(query: str, max_results: int) -> list[dict]:
    try:
        raw = await hal.search(query, max_results)
        if raw.startswith("No HAL"):
            return []
        return [{"source": "hal", "text": raw}]
    except Exception as e:
        logger.error(f"HAL search failed: {e}")
        return [{"source": "hal", "text": f"[HAL error: {e}]"}]


async def _search_pmc(query: str, max_results: int) -> list[dict]:
    try:
        raw = await pmc.search(query, max_results)
        if raw.startswith("No PMC"):
            return []
        return [{"source": "pmc", "text": raw}]
    except Exception as e:
        logger.error(f"PMC search failed: {e}")
        return [{"source": "pmc", "text": f"[PMC error: {e}]"}]


async def _search_doaj(query: str, max_results: int) -> list[dict]:
    try:
        raw = await doaj.search(query, max_results)
        if raw.startswith("No DOAJ"):
            return []
        return [{"source": "doaj", "text": raw}]
    except Exception as e:
        logger.error(f"DOAJ search failed: {e}")
        return [{"source": "doaj", "text": f"[DOAJ error: {e}]"}]


async def _search_zenodo(query: str, max_results: int) -> list[dict]:
    try:
        raw = await zenodo.search(query, max_results)
        if raw.startswith("No Zenodo"):
            return []
        return [{"source": "zenodo", "text": raw}]
    except Exception as e:
        logger.error(f"Zenodo search failed: {e}")
        return [{"source": "zenodo", "text": f"[Zenodo error: {e}]"}]


async def _search_openaire(query: str, max_results: int) -> list[dict]:
    try:
        raw = await openaire.search(query, max_results)
        if raw.startswith("No OpenAIRE"):
            return []
        return [{"source": "openaire", "text": raw}]
    except Exception as e:
        logger.error(f"OpenAIRE search failed: {e}")
        return [{"source": "openaire", "text": f"[OpenAIRE error: {e}]"}]


async def _search_inspirehep(query: str, max_results: int) -> list[dict]:
    try:
        raw = await inspirehep.search(query, max_results)
        if raw.startswith("No INSPIRE"):
            return []
        return [{"source": "inspirehep", "text": raw}]
    except Exception as e:
        logger.error(f"INSPIRE-HEP search failed: {e}")
        return [{"source": "inspirehep", "text": f"[INSPIRE-HEP error: {e}]"}]


async def _search_chemrxiv(query: str, max_results: int) -> list[dict]:
    try:
        raw = await chemrxiv.search(query, max_results)
        if raw.startswith("No ChemRxiv"):
            return []
        return [{"source": "chemrxiv", "text": raw}]
    except Exception as e:
        logger.error(f"ChemRxiv search failed: {e}")
        return [{"source": "chemrxiv", "text": f"[ChemRxiv error: {e}]"}]


# ─── Class-based source wrappers ──────────────────────────────────────


async def _search_class_source(name: str, searcher_cls, query: str, max_results: int) -> list[dict]:
    """Generic wrapper for class-based PaperSource searchers."""
    try:
        searcher = searcher_cls()
        papers = await asyncio.to_thread(searcher.search, query, max_results=max_results)
        if not papers:
            return []
        lines = []
        for p in papers:
            line = f"**{p.title}**\n"
            authors = ", ".join(p.authors) if isinstance(p.authors, list) else str(p.authors)
            line += f"  Authors: {authors}\n"
            if p.doi:
                line += f"  DOI: {p.doi}\n"
            if p.url:
                line += f"  URL: {p.url}\n"
            if p.published_date:
                line += f"  Date: {p.published_date}\n"
            line += f"  Source: {p.source}"
            lines.append(line)
        header = f"## {name} Results ({len(lines)})\n\n"
        return [{"source": name, "text": header + "\n\n".join(lines)}]
    except NotImplementedError:
        return []
    except Exception as e:
        logger.error(f"{name} search failed: {e}")
        return [{"source": name, "text": f"[{name} error: {e}]"}]


async def _search_google_scholar(query: str, max_results: int) -> list[dict]:
    from .google_scholar import GoogleScholarSearcher
    return await _search_class_source("Google Scholar", GoogleScholarSearcher, query, max_results)


async def _search_iacr(query: str, max_results: int) -> list[dict]:
    from .iacr import IACRSearcher
    return await _search_class_source("IACR", IACRSearcher, query, max_results)


async def _search_core(query: str, max_results: int) -> list[dict]:
    from .core import CORESearcher
    return await _search_class_source("CORE", CORESearcher, query, max_results)


async def _search_citeseerx(query: str, max_results: int) -> list[dict]:
    from .citeseerx import CiteSeerXSearcher
    return await _search_class_source("CiteSeerX", CiteSeerXSearcher, query, max_results)


async def _search_ssrn(query: str, max_results: int) -> list[dict]:
    from .ssrn import SSRNSearcher
    return await _search_class_source("SSRN", SSRNSearcher, query, max_results)


async def _search_base(query: str, max_results: int) -> list[dict]:
    from .base_search import BASESearcher
    return await _search_class_source("BASE", BASESearcher, query, max_results)


async def _search_medrxiv(query: str, max_results: int) -> list[dict]:
    from .medrxiv import MedRxivSearcher
    return await _search_class_source("medRxiv", MedRxivSearcher, query, max_results)


SEARCH_DISPATCH = {
    # Original functional sources
    "arxiv": _search_arxiv,
    "dblp": _search_dblp,
    "scholar": _search_scholar,
    "pwc": _search_pwc,
    "hf": _search_hf,
    "ss": _search_ss,
    "crossref": _search_crossref,
    "openalex": _search_openalex,
    "pubmed": _search_pubmed,
    "biorxiv": _search_biorxiv,
    "europepmc": _search_europepmc,
    # Newly integrated functional sources
    "hal": _search_hal,
    "pmc": _search_pmc,
    "doaj": _search_doaj,
    "zenodo": _search_zenodo,
    "openaire": _search_openaire,
    "inspirehep": _search_inspirehep,
    "chemrxiv": _search_chemrxiv,
    # Class-based sources
    "google_scholar": _search_google_scholar,
    "iacr": _search_iacr,
    "core": _search_core,
    "citeseerx": _search_citeseerx,
    "ssrn": _search_ssrn,
    "base": _search_base,
    "medrxiv": _search_medrxiv,
}


async def search(
    query: str,
    sources: Optional[str] = None,
    max_results: int = 5,
) -> str:
    """
    Search for papers across multiple sources in parallel.

    Args:
        query: Search keywords.
        sources: Comma-separated list of sources to search.
                 Options: arxiv, dblp, scholar, pwc, hf, ss, crossref, openalex,
                 pubmed, biorxiv, europepmc, hal, pmc, doaj, zenodo, openaire,
                 inspirehep, google_scholar, iacr, core, citeseerx, ssrn, base,
                 medrxiv, chemrxiv.
                 Defaults to all sources.
        max_results: Max results per source (default 5).

    Returns:
        Merged results from all selected sources.
    """
    source_list = _parse_sources(sources)
    logger.info(f"Unified search '{query}' across: {source_list}")

    tasks = []
    for src in source_list:
        fn = SEARCH_DISPATCH.get(src)
        if fn:
            tasks.append(fn(query, max_results))

    all_results = await asyncio.gather(*tasks, return_exceptions=True)

    sections = []
    for result in all_results:
        if isinstance(result, Exception):
            sections.append(f"[Error: {result}]\n")
        elif isinstance(result, list):
            for item in result:
                sections.append(item["text"])

    if not sections:
        return f"No results found for '{query}' across {', '.join(source_list)}."

    header = f"# Unified Search: \"{query}\"\n**Sources:** {', '.join(source_list)} | **Max per source:** {max_results}\n"
    separator = "\n" + "─" * 60 + "\n"
    return header + separator + separator.join(sections)


async def download(paper_id: str) -> str:
    """
    Download a paper by its ID or URL. Auto-detects the source.

    Supported formats:
      - ArXiv ID: 2401.12345 or arxiv:2401.12345
      - ArXiv URL: https://arxiv.org/abs/2401.12345
      - DOI: 10.xxxx/... or https://doi.org/10.xxxx/...
      - Semantic Scholar ID (40-char hex)
      - Any PDF URL: https://example.com/paper.pdf

    Args:
        paper_id: Paper ID, ArXiv ID, DOI, or URL.

    Returns:
        Download status message.
    """
    source, clean_id = _detect_source(paper_id)
    logger.info(f"Unified download: detected source={source}, id={clean_id}")

    if source == "arxiv":
        return await arxiv.download_paper(clean_id)

    elif source == "openreview":
        # Download from OpenReview PDF URL
        pdf_url = f"https://openreview.net/pdf?id={clean_id}"
        return await _download_url(pdf_url, f"openreview_{clean_id}.pdf")

    elif source == "doi":
        # Resolve DOI to a PDF URL via doi.org redirect
        return await _download_url(f"https://doi.org/{clean_id}", f"doi_{clean_id.replace('/', '_')}.pdf")

    elif source == "ss":
        # Get paper info from Semantic Scholar, then try to download the PDF
        info = await semanticscholar.get_paper(clean_id)
        return info + "\n\n(Semantic Scholar does not host PDFs. Use the ArXiv ID or DOI above to download.)"

    elif source in ("url", "pwc_url", "hf_url", "dblp_url"):
        safe_name = re.sub(r'[^\w\-.]', '_', clean_id.split('/')[-1].split('?')[0])
        if not safe_name.endswith('.pdf'):
            safe_name += '.pdf'
        return await _download_url(clean_id, safe_name)

    else:
        return (
            f"Cannot download from source '{source}'. "
            f"Supported: ArXiv IDs, DOIs, URLs, or Semantic Scholar IDs."
        )


async def _download_url(url: str, filename: str) -> str:
    """Download a file from a URL to local storage."""
    import httpx
    storage = arxiv.STORAGE_PATH
    storage.mkdir(parents=True, exist_ok=True)

    pdf_path = storage / filename
    if pdf_path.exists():
        return f"Already downloaded: {pdf_path}"

    async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        pdf_path.write_bytes(resp.content)

    return f"Downloaded to {pdf_path} ({len(resp.content)} bytes)"


async def read(paper_id: str) -> str:
    """
    Read a paper's content. Auto-detects source from ID/URL format.

    Supported formats:
      - ArXiv ID: 2401.12345 (reads locally downloaded paper)
      - DOI: 10.xxxx/... (fetches metadata from CrossRef)
      - Semantic Scholar ID (fetches metadata + citations)
      - Any URL: fetches and extracts text from PDF/HTML

    Args:
        paper_id: Paper ID, DOI, or URL.

    Returns:
        Full text content or metadata of the paper.
    """
    source, clean_id = _detect_source(paper_id)
    logger.info(f"Unified read: detected source={source}, id={clean_id}")

    if source == "arxiv":
        return await arxiv.read_paper(clean_id)

    elif source in ("url", "pwc_url", "hf_url", "dblp_url", "openreview"):
        url = clean_id
        if source == "openreview":
            url = f"https://openreview.net/pdf?id={clean_id}"
        return await paperswithcode.read_paper_url(url)

    elif source == "dblp":
        return await dblp.bibtex(clean_id)

    elif source == "pwc":
        return await paperswithcode.get_paper(clean_id)

    elif source == "doi":
        return await crossref.get_by_doi(clean_id)

    elif source == "ss":
        return await semanticscholar.get_paper(clean_id)

    else:
        return (
            f"Cannot read from source '{source}'. "
            f"Try an ArXiv ID (download first), a DOI, or a direct PDF/HTML URL."
        )


async def list_papers(source: Optional[str] = None) -> str:
    """
    List available/downloaded papers across sources.

    Args:
        source: Optional filter — 'arxiv' for local downloads,
                'hf' for today's HuggingFace papers, or omit for all.

    Returns:
        List of available papers.
    """
    sections = []

    sources = _parse_sources(source) if source else ["arxiv", "hf"]

    tasks = {}
    if "arxiv" in sources:
        tasks["arxiv"] = arxiv.list_papers()
    if "hf" in sources:
        tasks["hf"] = huggingface.get_daily_papers()

    results = {}
    for key, coro in tasks.items():
        try:
            results[key] = await coro
        except Exception as e:
            results[key] = f"[{key} error: {e}]"

    if "arxiv" in results:
        sections.append(f"## Local Downloads (ArXiv)\n{results['arxiv']}")
    if "hf" in results:
        sections.append(f"## Today's HuggingFace Papers\n{results['hf']}")

    if not sections:
        return "No papers available. Use `search` to find papers and `download` to save them."

    return "\n\n" + "─" * 60 + "\n\n".join(sections)

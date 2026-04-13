# PaperMCP — All-in-One Academic Paper MCP Server

Unified MCP server combining **30+ academic paper sources** into 4 clean tools.
Search, download, and read papers from ArXiv, PubMed, Semantic Scholar, CrossRef,
Google Scholar, DBLP, OpenAlex, and many more — all through a single interface.

## Supported Sources

| # | Source | Type | Auth |
|---|--------|------|------|
| 1 | **ArXiv** | Preprints (CS, Physics, Math) | Free |
| 2 | **PubMed** | Biomedical literature | Free |
| 3 | **Semantic Scholar** | AI-powered academic search | Free |
| 4 | **CrossRef** | DOI metadata | Free |
| 5 | **OpenAlex** | Open scholarly metadata | Free |
| 6 | **DBLP** | Computer science bibliography | Free |
| 7 | **Google Scholar** | Web scraping (scholarly lib) | Free |
| 8 | **Google Scholar (HTML)** | Direct HTML parsing | Free |
| 9 | **bioRxiv** | Biology preprints | Free |
| 10 | **medRxiv** | Medical preprints | Free |
| 11 | **Europe PMC** | European biomedical literature | Free |
| 12 | **PubMed Central** | Full-text biomedical articles | Free |
| 13 | **HuggingFace** | Daily trending AI papers | Free |
| 14 | **PapersWithCode** | ML papers with code | Free |
| 15 | **OpenReview** | Conference papers | Free |
| 16 | **HAL** | French national open archive | Free |
| 17 | **DOAJ** | Open access journals | Free |
| 18 | **Zenodo** | Open research data | Free |
| 19 | **OpenAIRE** | European open access | Free |
| 20 | **INSPIRE-HEP** | High energy physics | Free |
| 21 | **Unpaywall** | Open access DOI resolver | Free |
| 22 | **IACR** | Cryptography ePrint archive | Free |
| 23 | **CORE** | Global open access aggregator | API key (opt.) |
| 24 | **CiteSeerX** | CS digital library | Free |
| 25 | **SSRN** | Social science preprints | Free |
| 26 | **BASE** | Bielefeld Academic Search Engine | Free |
| 27 | **ChemRxiv** | Chemistry preprints | Free |
| 28 | **Sci-Hub** | PDF fetcher (CLI only) | Free |
| 29 | **IEEE Xplore** | Engineering (skeleton) | API key |
| 30 | **ACM DL** | Computing (skeleton) | API key |

## Quick Start

### Install
```bash
pip install -e .
# or
uv pip install -e .
```

### Run MCP Server
```bash
paper-mcp
# or
python -m paper_mcp
```

### CLI Usage
```bash
# Search across all sources
paper-search search "transformer architectures" -n 5

# Search specific sources
paper-search search "CRISPR" -s pubmed,biorxiv,europepmc

# Download a paper
paper-search download arxiv 2401.12345

# Read paper text
paper-search read arxiv 2401.12345

# List available sources
paper-search sources
```

## Unified MCP Tools

### `search(query, sources?, max_results?)`
Search for papers across all sources in parallel. Returns merged results.

### `download(paper_id)`
Download a paper by ID or URL. Auto-detects source from format:
- ArXiv ID: `2401.12345` or `arxiv:2401.12345`
- DOI: `10.xxxx/...`
- URL: any `https://...` link

### `read(paper_id)`
Read a paper's full text or metadata. Auto-detects source.

### `list_papers(source?)`
List locally downloaded papers and today's HuggingFace trending papers.

## Source Aliases

| Alias | Source |
|-------|--------|
| `arxiv` | ArXiv |
| `ss`, `s2`, `semanticscholar` | Semantic Scholar |
| `scholar`, `google` | Google Scholar (scholarly) |
| `google_scholar` | Google Scholar (HTML) |
| `crossref`, `cr` | CrossRef |
| `openalex`, `oa` | OpenAlex |
| `pubmed`, `pm` | PubMed |
| `pmc`, `pubmedcentral` | PubMed Central |
| `biorxiv` | bioRxiv |
| `medrxiv` | medRxiv |
| `europepmc`, `epmc` | Europe PMC |
| `hf`, `huggingface` | HuggingFace |
| `pwc`, `paperswithcode` | PapersWithCode |
| `dblp` | DBLP |
| `hal` | HAL |
| `doaj` | DOAJ |
| `zenodo` | Zenodo |
| `openaire` | OpenAIRE |
| `inspirehep`, `inspire` | INSPIRE-HEP |
| `iacr` | IACR ePrint |
| `core` | CORE |
| `citeseerx` | CiteSeerX |
| `ssrn` | SSRN |
| `base` | BASE |
| `chemrxiv` | ChemRxiv |
| `unpaywall` | Unpaywall |

## Configuration

### MCP Client (Claude Desktop / VS Code)

```json
{
  "mcpServers": {
    "paper-mcp": {
      "command": "paper-mcp"
    }
  }
}
```

### Environment Variables

```bash
# Storage path for downloaded papers
PAPER_MCP_STORAGE=~/.paper-mcp/papers

# OpenReview credentials (optional)
OPENREVIEW_USERNAME=
OPENREVIEW_PASSWORD=

# Optional API keys for enhanced sources
PAPER_SEARCH_MCP_CORE_API_KEY=       # CORE API
PAPER_SEARCH_MCP_UNPAYWALL_EMAIL=    # Unpaywall (polite pool)
PAPER_SEARCH_MCP_IEEE_API_KEY=       # IEEE Xplore
PAPER_SEARCH_MCP_ACM_API_KEY=        # ACM Digital Library
PAPER_SEARCH_MCP_GOOGLE_SCHOLAR_PROXY_URL=  # Google Scholar proxy
```

## Docker

```bash
docker build -t paper-mcp .
docker run -it paper-mcp
```

## Project Structure

```
src/paper_mcp/
├── __init__.py          # Package entry point
├── __main__.py          # python -m paper_mcp
├── server.py            # FastMCP server (4 unified tools)
├── cli.py               # CLI interface (paper-search command)
├── paper.py             # Paper dataclass model
├── config.py            # Environment configuration
├── utils.py             # DOI extraction utilities
└── sources/
    ├── unified.py       # Parallel search dispatcher
    ├── base.py          # Abstract PaperSource base class
    ├── oaipmh.py        # OAI-PMH protocol base
    ├── arxiv.py         # ArXiv
    ├── pubmed.py        # PubMed
    ├── semanticscholar.py # Semantic Scholar
    ├── crossref.py      # CrossRef
    ├── openalex.py      # OpenAlex
    ├── dblp.py          # DBLP
    ├── scholar.py       # Google Scholar (scholarly)
    ├── google_scholar.py # Google Scholar (HTML)
    ├── biorxiv.py       # bioRxiv
    ├── medrxiv.py       # medRxiv
    ├── europepmc.py     # Europe PMC
    ├── pmc.py           # PubMed Central
    ├── huggingface.py   # HuggingFace Daily Papers
    ├── paperswithcode.py # PapersWithCode
    ├── openreview.py    # OpenReview
    ├── hal.py           # HAL
    ├── doaj.py          # DOAJ
    ├── zenodo.py        # Zenodo
    ├── openaire.py      # OpenAIRE
    ├── inspirehep.py    # INSPIRE-HEP
    ├── unpaywall.py     # Unpaywall
    ├── iacr.py          # IACR ePrint
    ├── core.py          # CORE
    ├── citeseerx.py     # CiteSeerX
    ├── ssrn.py          # SSRN
    ├── base_search.py   # BASE
    ├── chemrxiv.py      # ChemRxiv
    ├── sci_hub.py       # Sci-Hub
    ├── ieee.py          # IEEE Xplore (skeleton)
    └── acm.py           # ACM DL (skeleton)
```

## License

MIT

#!/usr/bin/env python3
"""
Discover similar academic-paper MCP servers on GitHub.

Searches GitHub for repositories that look like MCP servers providing
academic paper functionality, filters for ones that don't require
authentication, and outputs a JSON report.

Usage:
    python scripts/discover_mcps.py [--token GITHUB_TOKEN] [--output report.json]

Environment:
    GITHUB_TOKEN   Optional – raises rate-limit from 10 → 30 req/min.
"""

import argparse
import json
import logging
import os
import sys
import time
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"

# Queries designed to find MCP servers related to academic papers
SEARCH_QUERIES = [
    "mcp server academic paper",
    "mcp server arxiv",
    "mcp server scholarly",
    "mcp server research paper",
    "model context protocol paper",
    "model context protocol arxiv",
    "model context protocol academic",
    "mcp paper search tool",
]

# Our own repo — skip it in results
OWN_REPO = "ScienceAIHub/PaperMCP"

# Rate-limit delay (seconds) between GitHub API requests
RATE_LIMIT_DELAY = 2

# Max characters of README to inspect for heuristic checks
README_PREVIEW_LENGTH = 3000

# Keywords that suggest a repo requires authentication tokens
AUTH_KEYWORDS = [
    "api_key", "api-key", "apikey",
    "access_token", "secret_key",
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
    "requires authentication", "requires an api key",
]


def _gh_get(path: str, token: str | None = None) -> Any:
    """Make a GET request to the GitHub API with optional token."""
    url = f"{GITHUB_API}{path}" if path.startswith("/") else path
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except HTTPError as exc:
        if exc.code == 403:
            logger.warning("GitHub API rate-limited — sleeping 60s")
            time.sleep(60)
            with urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        raise


def _search_repos(query: str, token: str | None) -> list[dict]:
    """Search GitHub repositories for a query string."""
    encoded_q = query.replace(" ", "+")
    path = f"/search/repositories?q={encoded_q}+in:name,description,readme&sort=updated&per_page=30"
    try:
        data = _gh_get(path, token)
        return data.get("items", [])
    except Exception as exc:
        logger.error("Search failed for %r: %s", query, exc)
        return []


def _get_readme(full_name: str, token: str | None) -> str:
    """Fetch the README content of a repository (decoded)."""
    try:
        data = _gh_get(f"/repos/{full_name}/readme", token)
        import base64
        return base64.b64decode(data.get("content", "")).decode(errors="replace")
    except Exception:
        return ""


def _appears_auth_free(readme: str, description: str) -> bool:
    """Heuristic: does the repo appear to work without API keys?"""
    combined = (readme + " " + (description or "")).lower()
    for kw in AUTH_KEYWORDS:
        if kw.lower() in combined:
            return False
    return True


def _is_mcp_repo(repo: dict, readme: str) -> bool:
    """Heuristic: does this repo look like an MCP server?"""
    combined = (
        (repo.get("description") or "")
        + " "
        + " ".join(repo.get("topics", []))
        + " "
        + readme[:README_PREVIEW_LENGTH]
    ).lower()
    has_mcp = "mcp" in combined or "model context protocol" in combined
    has_paper = any(
        kw in combined
        for kw in ["paper", "arxiv", "scholar", "academic", "research", "pubmed"]
    )
    return has_mcp and has_paper


def discover(token: str | None = None) -> list[dict]:
    """
    Run all search queries and return de-duplicated candidate repos.

    Returns a list of dicts with keys:
        full_name, url, description, stars, updated_at, auth_free, topics
    """
    seen: set[str] = set()
    candidates: list[dict] = []

    for query in SEARCH_QUERIES:
        logger.info("Searching: %s", query)
        repos = _search_repos(query, token)
        # Pause between searches to avoid rate-limiting
        time.sleep(RATE_LIMIT_DELAY)

        for repo in repos:
            full_name = repo["full_name"]
            if full_name in seen or full_name == OWN_REPO:
                continue
            seen.add(full_name)

            readme = _get_readme(full_name, token)
            time.sleep(RATE_LIMIT_DELAY)  # rate-limit courtesy

            if not _is_mcp_repo(repo, readme):
                continue

            auth_free = _appears_auth_free(readme, repo.get("description", ""))

            candidates.append({
                "full_name": full_name,
                "url": repo["html_url"],
                "description": repo.get("description", ""),
                "stars": repo.get("stargazers_count", 0),
                "updated_at": repo.get("updated_at", ""),
                "auth_free": auth_free,
                "topics": repo.get("topics", []),
                "language": repo.get("language", ""),
            })

    # Sort: auth-free first, then by stars descending
    candidates.sort(key=lambda c: (not c["auth_free"], -c["stars"]))
    return candidates


def main():
    parser = argparse.ArgumentParser(description="Discover similar MCP repos on GitHub")
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""),
                        help="GitHub personal access token (or set GITHUB_TOKEN)")
    parser.add_argument("--output", default="mcp_discovery_report.json",
                        help="Output file path")
    args = parser.parse_args()

    token = args.token or None
    candidates = discover(token)

    logger.info("Found %d candidate MCP repos", len(candidates))
    for c in candidates:
        tag = "✅ no-auth" if c["auth_free"] else "🔑 needs-auth"
        logger.info("  %s [%s] ⭐%d — %s", c["full_name"], tag, c["stars"], c["description"][:80])

    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_candidates": len(candidates),
        "auth_free_count": sum(1 for c in candidates if c["auth_free"]),
        "candidates": candidates,
    }

    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)
    logger.info("Report written to %s", args.output)

    # Print summary to stdout for CI
    print(f"\n{'='*60}")
    print(f"MCP Discovery Report — {report['timestamp']}")
    print(f"{'='*60}")
    print(f"Total candidates found: {report['total_candidates']}")
    print(f"Auth-free candidates:   {report['auth_free_count']}")
    print()
    for i, c in enumerate(candidates[:20], 1):
        tag = "no-auth" if c["auth_free"] else "needs-auth"
        print(f"  {i:2d}. {c['full_name']:<40s} ⭐{c['stars']:>4d}  [{tag}]")
        print(f"      {c['description'][:70]}")
        print(f"      {c['url']}")
        print()

    return 0 if candidates else 1


if __name__ == "__main__":
    sys.exit(main())

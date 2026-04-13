#!/usr/bin/env python3
"""
Evaluate discovered MCP candidates for potential integration.

Clones the top auth-free candidate repos, checks if they contain
paper-source modules that could be adapted for PaperMCP, and outputs
a structured evaluation report.

Usage:
    python scripts/evaluate_candidates.py \
        --report mcp_discovery_report.json \
        --max-candidates 5
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import Request, urlopen

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"

# Rate-limit delay (seconds) between GitHub API / clone requests
RATE_LIMIT_DELAY = 2

# Max characters of source file to read for heuristic analysis
CONTENT_PREVIEW_LENGTH = 5000

# Patterns that indicate useful source modules
SOURCE_PATTERNS = [
    "arxiv", "scholar", "pubmed", "crossref", "openalex",
    "semantic_scholar", "semanticscholar", "biorxiv", "medrxiv",
    "europepmc", "dblp", "paperswithcode", "ieee", "scopus",
    "springer", "nature", "acm", "wos", "web_of_science",
    "core", "base_search", "dimensions", "lens",
]

# Sources we already have
EXISTING_SOURCES = {
    "arxiv", "dblp", "scholar", "paperswithcode", "huggingface",
    "semanticscholar", "crossref", "openalex", "pubmed",
    "biorxiv", "europepmc", "openreview", "zenodo", "unpaywall",
    "hal", "openaire", "inspirehep", "doaj", "pmc",
}


def _gh_get(url: str, token: str | None = None):
    """GET request to GitHub API."""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(url if url.startswith("http") else f"{GITHUB_API}{url}",
                  headers=headers)
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def _clone_repo(clone_url: str, dest: Path) -> bool:
    """Shallow-clone a repo. Returns True on success."""
    try:
        subprocess.run(
            ["git", "clone", "--depth=1", clone_url, str(dest)],
            capture_output=True, text=True, timeout=120, check=True,
        )
        return True
    except Exception as exc:
        logger.error("Clone failed for %s: %s", clone_url, exc)
        return False


def _find_python_sources(repo_dir: Path) -> list[dict]:
    """Find Python files that look like paper-source modules."""
    sources_found = []
    for py_file in repo_dir.rglob("*.py"):
        name = py_file.stem.lower()
        rel = str(py_file.relative_to(repo_dir))

        # Skip tests, setup files, etc.
        if any(skip in rel for skip in ["test", "setup.py", "conftest", "__pycache__"]):
            continue

        for pattern in SOURCE_PATTERNS:
            if pattern in name:
                # Read first 50 lines to check for search-like functions
                try:
                    content = py_file.read_text(errors="replace")[:CONTENT_PREVIEW_LENGTH]
                except Exception:
                    content = ""

                has_search = "async def search" in content or "def search" in content
                has_httpx = "httpx" in content or "requests" in content or "aiohttp" in content
                is_new = pattern not in EXISTING_SOURCES

                sources_found.append({
                    "file": rel,
                    "pattern": pattern,
                    "has_search_func": has_search,
                    "has_http_client": has_httpx,
                    "is_new_source": is_new,
                    "preview": content[:500],
                })
                break

    return sources_found


def _check_tests(repo_dir: Path) -> dict:
    """Check if the repo has tests and try running them."""
    has_tests = any(repo_dir.rglob("test_*.py")) or any(repo_dir.rglob("*_test.py"))
    has_pytest = (repo_dir / "pyproject.toml").exists() or (repo_dir / "setup.py").exists()

    result = {"has_tests": has_tests, "has_build_config": has_pytest}

    if has_tests and has_pytest:
        try:
            proc = subprocess.run(
                ["python", "-m", "pytest", "--co", "-q"],
                capture_output=True, text=True, timeout=30,
                cwd=str(repo_dir),
            )
            result["test_collection"] = proc.stdout[:500]
            result["test_collection_ok"] = proc.returncode == 0
        except Exception as exc:
            result["test_collection"] = str(exc)
            result["test_collection_ok"] = False

    return result


def evaluate_candidate(candidate: dict, token: str | None = None) -> dict:
    """Evaluate a single candidate repository."""
    full_name = candidate["full_name"]
    logger.info("Evaluating: %s", full_name)

    evaluation = {
        "full_name": full_name,
        "url": candidate["url"],
        "stars": candidate["stars"],
        "auth_free": candidate["auth_free"],
        "cloned": False,
        "sources_found": [],
        "new_sources": [],
        "test_info": {},
        "recommendation": "skip",
        "reason": "",
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir) / full_name.replace("/", "_")
        clone_url = f"https://github.com/{full_name}.git"

        if not _clone_repo(clone_url, repo_dir):
            evaluation["reason"] = "Clone failed"
            return evaluation

        evaluation["cloned"] = True

        # Find source modules
        sources = _find_python_sources(repo_dir)
        evaluation["sources_found"] = [
            {k: v for k, v in s.items() if k != "preview"} for s in sources
        ]

        # Identify genuinely new sources we don't already have
        new_sources = [s for s in sources if s["is_new_source"] and s["has_search_func"]]
        evaluation["new_sources"] = [
            {k: v for k, v in s.items() if k != "preview"} for s in new_sources
        ]

        # Check tests
        evaluation["test_info"] = _check_tests(repo_dir)

        # Make recommendation
        if new_sources:
            evaluation["recommendation"] = "integrate"
            evaluation["reason"] = (
                f"Found {len(new_sources)} new source(s) with search functions: "
                + ", ".join(s["pattern"] for s in new_sources)
            )
        elif sources:
            evaluation["recommendation"] = "review"
            evaluation["reason"] = (
                f"Found {len(sources)} source(s) but all overlap with existing sources"
            )
        else:
            evaluation["recommendation"] = "skip"
            evaluation["reason"] = "No compatible paper-source modules found"

    return evaluation


def main():
    parser = argparse.ArgumentParser(description="Evaluate discovered MCP candidates")
    parser.add_argument("--report", required=True, help="Path to discovery report JSON")
    parser.add_argument("--max-candidates", type=int, default=5,
                        help="Max candidates to evaluate")
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""),
                        help="GitHub token")
    args = parser.parse_args()

    with open(args.report) as f:
        report = json.load(f)

    # Evaluate top auth-free candidates
    candidates = [c for c in report["candidates"] if c["auth_free"]]
    candidates = candidates[: args.max_candidates]

    if not candidates:
        logger.info("No auth-free candidates to evaluate.")
        print("No auth-free candidates found for evaluation.")
        return 0

    logger.info("Evaluating %d auth-free candidates", len(candidates))

    evaluations = []
    for c in candidates:
        ev = evaluate_candidate(c, args.token or None)
        evaluations.append(ev)
        time.sleep(RATE_LIMIT_DELAY)  # Rate-limit courtesy

    # Print summary
    print(f"\n{'='*60}")
    print("MCP Candidate Evaluation Summary")
    print(f"{'='*60}\n")

    for ev in evaluations:
        icon = {"integrate": "🟢", "review": "🟡", "skip": "⚪"}.get(
            ev["recommendation"], "⚪"
        )
        print(f"{icon} {ev['full_name']} (⭐{ev['stars']})")
        print(f"   Recommendation: {ev['recommendation']}")
        print(f"   Reason: {ev['reason']}")
        if ev["new_sources"]:
            for ns in ev["new_sources"]:
                print(f"   → New source: {ns['pattern']} ({ns['file']})")
        print()

    # Write evaluation results
    eval_path = "mcp_evaluation_report.json"
    with open(eval_path, "w") as f:
        json.dump(evaluations, f, indent=2)
    logger.info("Evaluation report written to %s", eval_path)

    # Count integration candidates
    integrate_count = sum(1 for e in evaluations if e["recommendation"] == "integrate")
    print(f"Candidates recommended for integration: {integrate_count}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

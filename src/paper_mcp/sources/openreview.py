"""OpenReview source — search conference papers (ICLR, NeurIPS, ICML)."""

import logging
import os
import asyncio
from typing import Optional

logger = logging.getLogger("paper_mcp.openreview")


def _get_client():
    """Create an OpenReview API client."""
    import openreview
    return openreview.api.OpenReviewClient(
        baseurl=os.environ.get("OPENREVIEW_BASE_URL", "https://api2.openreview.net"),
        username=os.environ.get("OPENREVIEW_USERNAME"),
        password=os.environ.get("OPENREVIEW_PASSWORD"),
    )


def _get_conference_papers(venue: str, year: str, limit: int = 50) -> list[dict]:
    """Get papers from a conference venue and year."""
    client = _get_client()
    venue_id = f"{venue}/{year}/Conference"

    try:
        submissions = client.get_all_notes(content={"venueid": venue_id})
    except Exception:
        try:
            submissions = client.get_all_notes(
                invitation=f"{venue_id}/-/Blind_Submission",
                details="original",
            )
        except Exception:
            submissions = client.get_all_notes(
                invitation=f"{venue_id}/-/Submission",
            )

    papers = []
    for sub in submissions[:limit]:
        try:
            content = sub.content
            title = _extract(content.get("title"))
            authors = _extract(content.get("authors", []))
            abstract = _extract(content.get("abstract", ""))
            if isinstance(authors, str):
                authors = [authors]

            papers.append({
                "id": sub.id,
                "title": title,
                "authors": authors,
                "abstract": abstract,
                "venue": venue_id,
                "url": f"https://openreview.net/forum?id={sub.id}",
                "pdf_url": f"https://openreview.net/pdf?id={sub.id}",
            })
        except Exception as e:
            logger.debug(f"Skip submission: {e}")

    return papers


def _search_in_papers(papers: list[dict], query: str, match_mode: str = "all") -> list[dict]:
    """Search through papers by keyword matching."""
    terms = [t.strip().lower() for t in query.split() if t.strip()]
    if not terms:
        return papers

    results = []
    for paper in papers:
        searchable = f"{paper['title']} {paper['abstract']}".lower()
        if match_mode == "all":
            if all(t in searchable for t in terms):
                results.append(paper)
        elif match_mode == "any":
            if any(t in searchable for t in terms):
                results.append(paper)
        elif match_mode == "exact":
            if query.lower() in searchable:
                results.append(paper)

    return results


def _extract(field):
    """Extract value from field that might be a dict with 'value' key."""
    if isinstance(field, dict):
        return field.get("value", field)
    return field


def _find_user(email: str) -> Optional[dict]:
    """Find a user profile by email."""
    import openreview.tools
    client = _get_client()
    try:
        profiles = openreview.tools.get_profiles(
            client, [email], as_dict=True, with_publications=True
        )
        if not profiles:
            return None

        pid = list(profiles.keys())[0]
        profile = profiles[pid]
        name = profile.content.get("name")
        if isinstance(name, dict):
            name = name.get("value", str(name))

        return {
            "id": pid,
            "email": email,
            "name": name,
        }
    except Exception as e:
        return {"error": str(e)}


def _get_user_papers(email: str) -> list[dict]:
    """Get papers by a user from their profile."""
    import openreview.tools
    client = _get_client()
    try:
        profiles = openreview.tools.get_profiles(
            client, [email], as_dict=True, with_publications=True
        )
        if not profiles:
            return []

        pid = list(profiles.keys())[0]
        profile = profiles[pid]
        papers = []

        for pub in profile.content.get("publications", []):
            try:
                content = pub.content
                title = _extract(content.get("title", ""))
                authors = _extract(content.get("authors", []))
                abstract = _extract(content.get("abstract", ""))
                if isinstance(authors, str):
                    authors = [authors]

                papers.append({
                    "id": pub.id,
                    "title": title,
                    "authors": authors,
                    "abstract": abstract,
                    "url": f"https://openreview.net/forum?id={pub.id}",
                })
            except Exception:
                continue

        return papers
    except Exception as e:
        logger.error(f"Error getting user papers: {e}")
        return []


async def search_papers(
    query: str,
    venues: list[dict],
    match_mode: str = "all",
    limit: int = 20,
) -> str:
    """Search papers by keywords across OpenReview conferences."""
    all_papers = []

    def _do_search():
        for v in venues:
            venue = v.get("venue", "")
            year = v.get("year", "")
            if venue and year:
                papers = _get_conference_papers(venue, year, limit=500)
                matched = _search_in_papers(papers, query, match_mode)
                all_papers.extend(matched[:limit])
        return all_papers[:limit]

    results = await asyncio.to_thread(_do_search)

    if not results:
        return f"No papers found for '{query}' in the specified venues."

    lines = [f"OpenReview results for '{query}' — {len(results)} papers:\n"]
    for p in results:
        lines.append(f"**{p['title']}**")
        lines.append(f"  Authors: {', '.join(p['authors'][:5])}")
        lines.append(f"  Venue: {p['venue']}")
        lines.append(f"  Abstract: {p['abstract'][:200]}...")
        lines.append(f"  URL: {p['url']}")
        lines.append("")

    return "\n".join(lines)


async def conference_papers(venue: str, year: str, limit: int = 50) -> str:
    """Get papers from a specific OpenReview conference (e.g., ICLR.cc, NeurIPS.cc, ICML.cc)."""
    papers = await asyncio.to_thread(_get_conference_papers, venue, year, limit)

    if not papers:
        return f"No papers found for {venue}/{year}."

    lines = [f"OpenReview papers from {venue}/{year} — {len(papers)} papers:\n"]
    for p in papers:
        lines.append(f"**{p['title']}**")
        lines.append(f"  Authors: {', '.join(p['authors'][:5])}")
        lines.append(f"  URL: {p['url']}")
        lines.append("")

    return "\n".join(lines)


async def search_user(email: str) -> str:
    """Find an OpenReview user profile by email."""
    user = await asyncio.to_thread(_find_user, email)
    if not user:
        return f"No user found for email: {email}"
    if "error" in user:
        return f"Error: {user['error']}"

    return f"**{user['name']}**\n  ID: {user['id']}\n  Email: {user['email']}"


async def user_papers(email: str) -> str:
    """Get all papers by a user from OpenReview."""
    papers = await asyncio.to_thread(_get_user_papers, email)
    if not papers:
        return f"No papers found for {email}."

    lines = [f"Papers by {email} — {len(papers)} papers:\n"]
    for p in papers:
        lines.append(f"**{p['title']}**")
        lines.append(f"  Authors: {', '.join(p['authors'][:5])}")
        lines.append(f"  URL: {p['url']}")
        lines.append("")

    return "\n".join(lines)

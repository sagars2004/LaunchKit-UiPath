"""Devpost scraper and RPA data formatter."""

import logging
import re

import httpx
from bs4 import BeautifulSoup

from backend.core.exceptions import AgentError
from backend.models.content import DevpostCopy

logger = logging.getLogger("launchkit.devpost")

USER_AGENT = "LaunchKit/0.1 (hackathon submission pipeline)"


class DevpostService:
    """Scrape Devpost pages and format copy for UiPath RPA."""

    async def scrape_submission_page(self, devpost_url: str) -> dict:
        """Scrape a Devpost project submission page."""
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(
                    devpost_url,
                    headers={"User-Agent": USER_AGENT},
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AgentError(f"Failed to fetch Devpost page: {devpost_url}", str(exc)) from exc

        soup = BeautifulSoup(response.text, "html.parser")

        def text(sel: str) -> str:
            el = soup.select_one(sel)
            return el.get_text(strip=True) if el else ""

        project_name = text("h1") or text(".app-title")
        tagline = text(".tagline") or text("h2")

        built_with = [
            t.get_text(strip=True)
            for t in soup.select(
                ".software-built-with a, .built-with a, [data-role='built-with'] a"
            )
        ]

        sections: dict[str, str] = {}
        for heading in soup.select("h2, h3, .content-title"):
            title = heading.get_text(strip=True).lower()
            sibling = heading.find_next_sibling(["p", "div"])
            if sibling:
                sections[title] = sibling.get_text(strip=True)[:2000]

        return {
            "url": devpost_url,
            "project_name": project_name,
            "tagline": tagline,
            "built_with": built_with,
            "sections": sections,
            "raw_text": soup.get_text(separator="\n", strip=True)[:8000],
        }

    async def scrape_event_page(self, event_url: str) -> str:
        """Fetch raw text from a Devpost event/hackathon page."""
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(
                    event_url,
                    headers={"User-Agent": USER_AGENT},
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AgentError(f"Failed to fetch event page: {event_url}", str(exc)) from exc

        soup = BeautifulSoup(response.text, "html.parser")

        criteria_section = ""
        for heading in soup.find_all(["h2", "h3", "h4", "strong"]):
            text = heading.get_text(strip=True).lower()
            if any(kw in text for kw in ("judging", "criteria", "evaluation", "rubric")):
                parent = heading.find_parent(["section", "div"]) or heading.parent
                if parent:
                    criteria_section = parent.get_text(separator="\n", strip=True)
                    break

        if criteria_section:
            return criteria_section

        for script in soup(["script", "style", "nav", "footer"]):
            script.decompose()
        return soup.get_text(separator="\n", strip=True)[:12000]

    async def search_submissions(self, query: str, limit: int = 5) -> list[str]:
        """Search Devpost and return submission page URLs."""
        search_url = f"https://devpost.com/software/search?query={query.replace(' ', '+')}"
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(
                    search_url,
                    headers={"User-Agent": USER_AGENT},
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Devpost search failed: %s", exc)
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        urls: list[str] = []
        for link in soup.select("a[href*='/software/']"):
            href = link.get("href", "")
            if re.match(r"https?://devpost\.com/software/[\w-]+", href):
                if href not in urls:
                    urls.append(href)
            elif href.startswith("/software/"):
                full = f"https://devpost.com{href}"
                if full not in urls:
                    urls.append(full)
            if len(urls) >= limit:
                break
        return urls[:limit]

    def format_for_rpa(self, devpost_copy: DevpostCopy) -> dict:
        """Format DevpostCopy into field-keyed dict for UiPath RPA bot."""
        return {
            "project_name": devpost_copy.project_name[:50],
            "tagline": devpost_copy.tagline[:100],
            "what_it_does": devpost_copy.what_it_does,
            "how_i_built_it": devpost_copy.how_i_built_it,
            "challenges": devpost_copy.challenges,
            "accomplishments": devpost_copy.accomplishments,
            "what_i_learned": devpost_copy.what_i_learned,
            "whats_next": devpost_copy.whats_next,
            "built_with": ", ".join(devpost_copy.built_with),
        }


def get_devpost_service() -> DevpostService:
    return DevpostService()

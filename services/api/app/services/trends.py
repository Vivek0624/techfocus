"""Where trend evidence comes from.

Two providers behind one interface:

  LiveSearchProvider   calls the Tavily-compatible JSON search endpoint already described in
                       .env.example (RESEARCH_API_URL / RESEARCH_API_KEY) and returns real hits
                       with real URLs.
  ModelKnowledgeProvider  returns nothing. The caller then writes topics from model knowledge only
                       and labels them "not live" everywhere they appear.

Nothing here writes to the database and nothing invents a result.
"""

from __future__ import annotations

import logging
from typing import Protocol

import httpx

from ..config import Settings

log = logging.getLogger(__name__)

SEARCH_TIMEOUT = 20.0
MAX_RESULTS = 8

NOT_LIVE = (
    "Model knowledge only, not live. These topics come from general knowledge of the niche and "
    "carry no sources. Check each one before you film."
)


class TrendProvider(Protocol):
    """One method: find evidence about what is getting attention in a niche right now."""

    name: str
    live: bool

    def search(self, niche: str, platform_label: str) -> list[dict]: ...


def _queries(niche: str, platform_label: str) -> list[str]:
    return [
        f"{niche} trending topics {platform_label} this month",
        f"{niche} what people are talking about right now",
        f"{niche} viral short video ideas recent",
    ]


class LiveSearchProvider:
    """Tavily-compatible POST: {query, max_results} -> {results: [{title, url, content}]}.

    Any endpoint with that shape works (Tavily, a self-hosted proxy, SearxNG behind an adapter).
    """

    name = "live_search"
    live = True

    def __init__(self, url: str, api_key: str | None):
        self.url = url
        self.api_key = api_key

    def search(self, niche: str, platform_label: str) -> list[dict]:
        out: list[dict] = []
        seen: set[str] = set()
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        with httpx.Client(timeout=SEARCH_TIMEOUT) as c:
            for q in _queries(niche, platform_label):
                body = {
                    "query": q,
                    "max_results": MAX_RESULTS,
                    "search_depth": "basic",
                    "topic": "news",
                    # Tavily also accepts the key in the body; harmless elsewhere.
                    **({"api_key": self.api_key} if self.api_key else {}),
                }
                try:
                    r = c.post(self.url, json=body, headers=headers)
                    r.raise_for_status()
                    data = r.json()
                except (httpx.HTTPError, ValueError) as e:
                    # One failing query must not lose the others.
                    log.warning("trend search failed for %r: %s", q, type(e).__name__)
                    continue
                for hit in data.get("results") or []:
                    url = (hit.get("url") or "").strip()
                    if not url or url in seen:
                        continue
                    seen.add(url)
                    out.append(
                        {
                            "title": (hit.get("title") or url)[:200],
                            "url": url,
                            "snippet": (hit.get("content") or hit.get("snippet") or "")[:700],
                            "published": hit.get("published_date") or hit.get("published") or None,
                        }
                    )
        return out[: MAX_RESULTS * 2]


class ModelKnowledgeProvider:
    """The clearly-marked fallback: no live data at all."""

    name = "model_knowledge"
    live = False

    def search(self, niche: str, platform_label: str) -> list[dict]:
        return []


def get_provider(s: Settings) -> TrendProvider:
    if s.research_api_url:
        key = s.research_api_key.get_secret_value() if s.research_api_key else None
        return LiveSearchProvider(s.research_api_url, key)
    return ModelKnowledgeProvider()

"""Instagram API with Instagram Login (graph.instagram.com).
Only endpoints recorded in docs/api-capabilities.md are implemented here."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import httpx

from ..config import Settings

log = logging.getLogger(__name__)

AUTHORIZE_URL = "https://www.instagram.com/oauth/authorize"
SHORT_TOKEN_URL = "https://api.instagram.com/oauth/access_token"

ACCOUNT_METRICS = [
    "reach",
    "views",
    "accounts_engaged",
    "total_interactions",
    "likes",
    "comments",
    "shares",
    "saves",
    "profile_links_taps",
]
REEL_METRICS = [
    "views",
    "reach",
    "likes",
    "comments",
    "shares",
    "saved",
    "total_interactions",
    "ig_reels_avg_watch_time",
    "ig_reels_video_view_total_time",
    "reposts",
]
# follows / profile_visits / profile_activity are reported for FEED posts and carousels only, not Reels.
FEED_METRICS = [
    "views",
    "reach",
    "likes",
    "comments",
    "shares",
    "saved",
    "total_interactions",
    "follows",
    "profile_visits",
    "profile_activity",
    "reposts",
]
# Newer or account-dependent metrics. If Instagram rejects the request because of one of these, it is retried
# without them so the core numbers still sync; the missing ones stay None (not reported), never 0.
OPTIONAL_MEDIA_METRICS = {
    "follows",
    "profile_visits",
    "profile_activity",
    "reposts",
    "ig_reels_video_view_total_time",
}


class InstagramAPIError(Exception):
    def __init__(
        self, message: str, status: int | None = None, code: int | None = None, retryable: bool = False
    ):
        super().__init__(message)
        self.status, self.code, self.retryable = status, code, retryable


class InstagramClientProto(Protocol):
    def get_profile(self) -> dict: ...
    def iter_media(self, limit: int = 50) -> Iterator[dict]: ...
    def media_insights(self, media_id: str, product_type: str | None) -> dict[str, int | None]: ...
    def account_insights(self, since: datetime, until: datetime) -> dict[str, int | None]: ...
    def follows_and_unfollows(self, since: datetime, until: datetime) -> dict[str, int | None]: ...
    def create_reel_container(self, video_url: str, caption: str) -> str: ...
    def container_status(self, container_id: str) -> str: ...
    def publish_container(self, container_id: str) -> str: ...
    def iter_comments(self, media_id: str, limit: int = 100) -> Iterator[dict]: ...
    def iter_replies(self, comment_id: str, limit: int = 50) -> Iterator[dict]: ...
    def create_image_container(
        self, image_url: str, caption: str | None, carousel_item: bool = False
    ) -> str: ...
    def create_video_item_container(self, video_url: str) -> str: ...
    def create_carousel_container(self, children: list[str], caption: str) -> str: ...
    def reply_to_comment(self, comment_id: str, message: str) -> str: ...
    def hide_comment(self, comment_id: str, hide: bool = True) -> bool: ...
    def iter_tags(self, limit: int = 50) -> Iterator[dict]: ...
    def demographics(self, breakdown: str) -> dict[str, int]: ...
    def online_followers(self) -> dict[str, int]: ...
    def publishing_limit(self) -> dict: ...


_PACIFIC, _IST = ZoneInfo("America/Los_Angeles"), ZoneInfo("Asia/Kolkata")


def pacific_hours_to_ist(hours: dict, end_time: str | None = None) -> dict[str, int]:
    """Re-key {hour: count} from US Pacific to IST (whole hours; IST's half hour rounds down). The day matters
    for daylight saving, so the value's end_time is used when present."""
    day = datetime.strptime(end_time[:10], "%Y-%m-%d") if end_time else datetime.now(UTC).replace(tzinfo=None)
    out: dict[str, int] = {}
    for k, n in hours.items():
        h = day.replace(hour=int(k), minute=0, second=0, microsecond=0, tzinfo=_PACIFIC).astimezone(_IST).hour
        out[str(h)] = out.get(str(h), 0) + int(n)
    return out


def authorize_url(s: Settings, state: str) -> str:
    q = {
        "client_id": s.meta_app_id,
        "redirect_uri": s.meta_redirect_uri,
        "response_type": "code",
        "scope": s.meta_scopes,
        "state": state,
        "enable_fb_login": "0",
        "force_reauth": "true",
    }
    return f"{AUTHORIZE_URL}?{urlencode(q)}"


def exchange_code(s: Settings, code: str, http: httpx.Client | None = None) -> dict:
    """code -> short-lived token -> long-lived (60 day) token."""
    c = http or httpx.Client(timeout=20)
    assert s.meta_app_secret is not None
    r = c.post(
        SHORT_TOKEN_URL,
        data={
            "client_id": s.meta_app_id,
            "client_secret": s.meta_app_secret.get_secret_value(),
            "grant_type": "authorization_code",
            "redirect_uri": s.meta_redirect_uri,
            "code": code,
        },
    )
    _raise(r)
    short = r.json()
    data = short["data"][0] if "data" in short else short
    r2 = c.get(
        f"{s.instagram_graph_base}/access_token",
        params={
            "grant_type": "ig_exchange_token",
            "client_secret": s.meta_app_secret.get_secret_value(),
            "access_token": data["access_token"],
        },
    )
    _raise(r2)
    long = r2.json()
    perms = data.get("permissions") or []
    if isinstance(perms, str):
        perms = perms.split(",")
    return {
        "access_token": long["access_token"],
        "expires_at": datetime.now(UTC) + timedelta(seconds=int(long.get("expires_in", 5184000))),
        "user_id": str(data.get("user_id", "")),
        "permissions": perms,
    }


def refresh_token(s: Settings, token: str, http: httpx.Client | None = None) -> dict:
    """Only valid for tokens >=24h old and not yet expired."""
    c = http or httpx.Client(timeout=20)
    r = c.get(
        f"{s.instagram_graph_base}/refresh_access_token",
        params={"grant_type": "ig_refresh_token", "access_token": token},
    )
    _raise(r)
    d = r.json()
    return {
        "access_token": d["access_token"],
        "expires_at": datetime.now(UTC) + timedelta(seconds=int(d.get("expires_in", 5184000))),
    }


def _raise(r: httpx.Response) -> None:
    if r.status_code < 400:
        return
    try:
        err = r.json().get("error", {})
    except ValueError:
        err = {}
    code = err.get("code")
    # 4, 17, 32, 613 are Meta rate-limit codes.
    retryable = r.status_code >= 500 or code in (4, 17, 32, 613)
    raise InstagramAPIError(err.get("message", f"HTTP {r.status_code}"), r.status_code, code, retryable)


class InstagramClient:
    def __init__(
        self,
        s: Settings,
        access_token: str,
        ig_user_id: str = "me",
        http: httpx.Client | None = None,
        max_retries: int = 3,
    ):
        self.base = f"{s.instagram_graph_base}/{s.instagram_api_version}"
        self.token = access_token
        self.uid = ig_user_id
        self.http = http or httpx.Client(timeout=30)
        self.max_retries = max_retries

    def _req(self, method: str, path: str, **params: Any) -> dict:
        url = path if path.startswith("http") else f"{self.base}/{path.lstrip('/')}"
        for attempt in range(self.max_retries + 1):
            q = dict(params)
            if not path.startswith("http"):
                q["access_token"] = self.token
            # Paging URLs from Meta already carry the cursor and token; passing params would replace them.
            r = self.http.request(
                method,
                url,
                params=(q or None) if method == "GET" else None,
                data=q if method != "GET" else None,
            )
            try:
                _raise(r)
                return r.json()
            except InstagramAPIError as e:
                if not e.retryable or attempt == self.max_retries:
                    raise
                time.sleep(min(30, 2**attempt))
        raise InstagramAPIError("unreachable")

    def _paginate(self, path: str, max_items: int, **params: Any) -> Iterator[dict]:
        got = 0
        page = self._req("GET", path, **params)
        while True:
            for item in page.get("data", []):
                yield item
                got += 1
                if got >= max_items:
                    return
            nxt = page.get("paging", {}).get("next")
            if not nxt:
                return
            page = self._req("GET", nxt)

    def get_profile(self) -> dict:
        return self._req(
            "GET",
            self.uid,
            fields="user_id,username,account_type,followers_count,"
            "follows_count,media_count,name,profile_picture_url",
        )

    def iter_media(self, limit: int = 50) -> Iterator[dict]:
        return self._paginate(
            f"{self.uid}/media",
            limit,
            limit=min(limit, 50),
            fields="id,caption,media_type,media_product_type,permalink,timestamp",
        )

    def media_insights(self, media_id: str, product_type: str | None) -> dict[str, int | None]:
        metrics = REEL_METRICS if product_type == "REELS" else FEED_METRICS
        try:
            d = self._req("GET", f"{media_id}/insights", metric=",".join(metrics))
        except InstagramAPIError as e:
            if e.retryable or e.status != 400:
                raise
            core = [m for m in metrics if m not in OPTIONAL_MEDIA_METRICS]
            log.info("optional media metrics rejected for %s, retrying core only: %s", media_id, e)
            d = self._req("GET", f"{media_id}/insights", metric=",".join(core))
        out: dict[str, int | None] = {m: None for m in metrics}
        for row in d.get("data", []):
            vals = row.get("values") or [{}]
            v = vals[0].get("value")
            if v is None:  # some metrics (profile_activity) come back as total_value
                v = (row.get("total_value") or {}).get("value")
            out[row["name"]] = v if isinstance(v, int) or v is None else None
        return out

    def account_insights(self, since: datetime, until: datetime) -> dict[str, int | None]:
        d = self._req(
            "GET",
            f"{self.uid}/insights",
            metric=",".join(ACCOUNT_METRICS),
            period="day",
            metric_type="total_value",
            since=int(since.timestamp()),
            until=int(until.timestamp()),
        )
        out: dict[str, int | None] = {m: None for m in ACCOUNT_METRICS}  # missing = unavailable, not 0
        for row in d.get("data", []):
            out[row["name"]] = (row.get("total_value") or {}).get("value")
        return out

    def follows_and_unfollows(self, since: datetime, until: datetime) -> dict[str, int | None]:
        """Unavailable for accounts under 100 followers."""
        try:
            d = self._req(
                "GET",
                f"{self.uid}/insights",
                metric="follows_and_unfollows",
                period="day",
                metric_type="total_value",
                breakdown="follow_type",
                since=int(since.timestamp()),
                until=int(until.timestamp()),
            )
        except InstagramAPIError as e:
            log.warning("follows_and_unfollows unavailable: %s", e)
            return {"follows": None, "unfollows": None}
        res: dict[str, int | None] = {"follows": None, "unfollows": None}
        for row in d.get("data", []):
            for b in (row.get("total_value") or {}).get("breakdowns", []):
                for r in b.get("results", []):
                    key = "follows" if r["dimension_values"][0] == "FOLLOWER" else "unfollows"
                    res[key] = r.get("value")
        return res

    def create_reel_container(self, video_url: str, caption: str) -> str:
        return self._req(
            "POST", f"{self.uid}/media", media_type="REELS", video_url=video_url, caption=caption
        )["id"]

    def create_image_container(self, image_url: str, caption: str | None, carousel_item: bool = False) -> str:
        """Single JPEG image post, or one image of a carousel (carousel_item=True, no caption)."""
        params: dict[str, Any] = {"image_url": image_url}
        if carousel_item:
            params["is_carousel_item"] = "true"
        elif caption:
            params["caption"] = caption
        return self._req("POST", f"{self.uid}/media", **params)["id"]

    def create_video_item_container(self, video_url: str) -> str:
        return self._req(
            "POST", f"{self.uid}/media", media_type="VIDEO", video_url=video_url, is_carousel_item="true"
        )["id"]

    def create_carousel_container(self, children: list[str], caption: str) -> str:
        return self._req(
            "POST", f"{self.uid}/media", media_type="CAROUSEL", children=",".join(children), caption=caption
        )["id"]

    def container_status(self, container_id: str) -> str:
        return self._req("GET", container_id, fields="status_code").get("status_code", "UNKNOWN")

    def publish_container(self, container_id: str) -> str:
        return self._req("POST", f"{self.uid}/media_publish", creation_id=container_id)["id"]

    # ---- comments, mentions, audience ----
    def iter_comments(self, media_id: str, limit: int = 100) -> Iterator[dict]:
        return self._paginate(
            f"{media_id}/comments", limit, fields="id,text,timestamp,username,like_count,hidden"
        )

    def iter_replies(self, comment_id: str, limit: int = 50) -> Iterator[dict]:
        """GET /{comment-id}/replies, so threads (including the account's own replies) are complete."""
        return self._paginate(
            f"{comment_id}/replies", limit, fields="id,text,timestamp,username,like_count,hidden"
        )

    def reply_to_comment(self, comment_id: str, message: str) -> str:
        return self._req("POST", f"{comment_id}/replies", message=message)["id"]

    def hide_comment(self, comment_id: str, hide: bool = True) -> bool:
        return bool(self._req("POST", comment_id, hide="true" if hide else "false").get("success", True))

    def iter_tags(self, limit: int = 50) -> Iterator[dict]:
        """Media the account was tagged in."""
        return self._paginate(f"{self.uid}/tags", limit, fields="id,caption,permalink,timestamp,username")

    def demographics(self, breakdown: str) -> dict[str, int]:
        """follower_demographics by age | gender | city | country. Needs >= 100 followers."""
        d = self._req(
            "GET",
            f"{self.uid}/insights",
            metric="follower_demographics",
            period="lifetime",
            metric_type="total_value",
            timeframe="this_month",
            breakdown=breakdown,
        )
        out: dict[str, int] = {}
        for row in d.get("data", []):
            for b in (row.get("total_value") or {}).get("breakdowns", []):
                for r in b.get("results", []):
                    out[r["dimension_values"][0]] = r.get("value", 0)
        return out

    def online_followers(self) -> dict[str, int]:
        """Followers online by hour, most recent day with data. Needs >= 100 followers.
        Instagram keys the hours in US Pacific time; they are converted to IST here so everything downstream is IST."""
        d = self._req("GET", f"{self.uid}/insights", metric="online_followers", period="lifetime")
        for row in d.get("data", []):
            for v in reversed(row.get("values", [])):
                if v.get("value"):
                    return pacific_hours_to_ist(v["value"], v.get("end_time"))
        return {}

    def publishing_limit(self) -> dict:
        return self._req("GET", f"{self.uid}/content_publishing_limit", fields="config,quota_usage")

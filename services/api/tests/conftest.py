import os
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp()
os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_URL": f"sqlite:///{_tmp}/test.db",
        "AGENT_MODE": "mock",
        "TOKEN_ENCRYPTION_KEY": "x2bUj3zGQd1PZ5nYh2tA3m1t7d8Ff6qY9sQyR0vTqKk=",
        "META_APP_ID": "123",
        "META_APP_SECRET": "test-secret",
        "AGENT_TIMEOUT_SECONDS": "5",
        "WEB_ORIGIN": "http://localhost:3000",
        "ENABLE_LOCAL_SCHEDULER": "false",
    }
)

import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from alembic import command  # noqa: E402
from app.config import get_settings  # noqa: E402

get_settings.cache_clear()


@pytest.fixture(scope="session", autouse=True)
def migrated():
    cfg = Config(str(Path(__file__).parent.parent / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).parent.parent / "alembic"))
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    command.upgrade(cfg, "head")
    yield cfg


@pytest.fixture()
def db():
    from app.db import SessionLocal

    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


class FakeIG:
    """Mock Instagram Graph client."""

    def __init__(self, followers=339, fail_publish=False):
        self.followers = followers
        self.fail_publish = fail_publish
        self.published = []

    def get_profile(self):
        return {
            "user_id": "17841400000000000",
            "username": "vivek_techfocus",
            "account_type": "MEDIA_CREATOR",
            "followers_count": self.followers,
        }

    def iter_media(self, limit=50):
        for i in range(3):
            yield {
                "id": f"m{i}",
                "caption": f"reel {i}",
                "media_type": "VIDEO",
                "media_product_type": "REELS",
                "permalink": f"https://instagram.com/reel/{i}",
                "timestamp": f"2026-10-1{i}T14:30:00+0000",
            }

    def media_insights(self, media_id, product_type):
        return {
            "views": 1000 + int(media_id[1:]) * 500,
            "reach": 800,
            "likes": 40,
            "comments": 3,
            "shares": 2,
            "saved": 5,
            "total_interactions": 50,
            "ig_reels_avg_watch_time": 6000,
            "ig_reels_video_view_total_time": 6000 * (1000 + int(media_id[1:]) * 500),
        }

    def account_insights(self, since, until):
        return {"reach": 1200, "views": 2000, "accounts_engaged": 60}  # others missing -> None

    def follows_and_unfollows(self, since, until):
        return {"follows": 12, "unfollows": 2}

    def create_reel_container(self, video_url, caption):
        return "container-1"

    def container_status(self, cid):
        return "FINISHED"

    def publish_container(self, cid):
        if self.fail_publish:
            from app.instagram.client import InstagramAPIError

            raise InstagramAPIError("boom")
        self.published.append(cid)
        return "media-999"

    def publishing_limit(self):
        return {}

    replies: list = []

    def iter_comments(self, media_id, limit=100):
        yield {
            "id": f"c-{media_id}-1",
            "text": "How do I start learning APIs?",
            "username": "asker",
            "timestamp": "2026-10-15T10:00:00+0000",
            "like_count": 3,
        }
        yield {
            "id": f"c-{media_id}-2",
            "text": "DM us for promotion",
            "username": "spammer",
            "timestamp": "2026-10-15T11:00:00+0000",
        }

    def iter_replies(self, comment_id, limit=50):
        if comment_id.endswith("-1"):
            yield {
                "id": f"{comment_id}-r1",
                "text": "Start with my API reel!",
                "username": "vivek_techfocus",
                "timestamp": "2026-10-15T12:00:00+0000",
            }

    def create_image_container(self, image_url, caption, carousel_item=False):
        self.containers = getattr(self, "containers", []) + [("image", image_url, carousel_item)]
        return f"img-{len(self.containers)}"

    def create_video_item_container(self, video_url):
        self.containers = getattr(self, "containers", []) + [("video", video_url, True)]
        return f"vid-{len(self.containers)}"

    def create_carousel_container(self, children, caption):
        self.carousel_children = children
        return "carousel-1"

    def reply_to_comment(self, comment_id, message):
        self.replies.append((comment_id, message))
        return "reply-1"

    def hide_comment(self, comment_id, hide=True):
        return True

    def iter_tags(self, limit=50):
        yield {
            "id": "tag-1",
            "username": "friend",
            "caption": "with @vivek_techfocus",
            "timestamp": "2026-10-14T10:00:00+0000",
        }

    def demographics(self, breakdown):
        from app.instagram.client import InstagramAPIError

        raise InstagramAPIError("Not enough followers")  # <100 followers: unavailable

    def online_followers(self):
        return {}


@pytest.fixture()
def fake_ig():
    return FakeIG()


@pytest.fixture()
def client(fake_ig):
    from app.db import SessionLocal
    from app.main import create_app

    app = create_app(SessionLocal, client_factory=lambda tok, uid: fake_ig)
    with TestClient(app) as c:
        yield c

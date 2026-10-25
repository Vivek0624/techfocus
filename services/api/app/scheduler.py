"""Local scheduler (APScheduler, in-process). Enabled with ENABLE_LOCAL_SCHEDULER=true.
It creates reminders and runs a READ-ONLY daily Instagram sync (profile, media, insights, comments, audience)
so follower history accumulates one snapshot per day. It never publishes, replies or hides anything."""

from __future__ import annotations

import fcntl
import logging
from collections.abc import Callable
from datetime import UTC, date, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from .models import CalendarItem, DailyTask, utcnow

log = logging.getLogger(__name__)


def remind_due_posts(sf: sessionmaker, horizon_minutes: int = 60) -> int:
    now = utcnow()
    n = 0
    with sf() as db:
        items = db.scalars(
            select(CalendarItem).where(
                CalendarItem.scheduled_at <= now + timedelta(minutes=horizon_minutes),
                CalendarItem.scheduled_at >= now - timedelta(minutes=5),
                CalendarItem.reminder_sent_at.is_(None),
                CalendarItem.publishing_status != "published",
            )
        )
        for it in items:
            it.reminder_sent_at = now
            db.add(
                DailyTask(
                    task_date=date.today(),
                    title=f"Post now: {it.title}"[:200],
                    reason="calendar reminder",
                    impact=3,
                    effort_minutes=10,
                    priority=99,
                    is_demo=it.is_demo,
                )
            )
            log.info("reminder created for calendar item %s", it.id)
            n += 1
        db.commit()
    return n


AUTO_SYNC_MIN_GAP = timedelta(hours=20)
_LOCK = Path(__file__).resolve().parent.parent / "data" / ".autosync.lock"


def auto_sync(sf: sessionmaker, client_factory: Callable, force: bool = False) -> dict:
    """Read-only daily sync of the connected account. Skips if synced in the last 20h. A file lock keeps the
    http and https API processes from syncing at the same time."""
    from .config import get_settings
    from .instagram import client as ig
    from .instagram import service as igs
    from .security import get_cipher
    from .services import queries as q
    from .services.activity import sync_activity

    _LOCK.parent.mkdir(parents=True, exist_ok=True)
    with open(_LOCK, "w") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return {"skipped": "another sync is running"}
        with sf() as db:
            acct = igs.live_account(db)
            if acct is None or acct.token is None:
                return {"skipped": "not connected"}
            last = acct.last_sync_at
            if last is not None and last.tzinfo is None:
                last = last.replace(tzinfo=UTC)
            if not force and last and utcnow() - last < AUTO_SYNC_MIN_GAP:
                return {"skipped": "synced recently"}
            if igs.token_status(acct)["state"] == "expired":
                q.set_setting(
                    db, "auto_sync", {"at": utcnow().isoformat(), "ok": False, "error": "token expired"}
                )
                db.commit()
                return {"skipped": "token expired"}
            cipher = get_cipher()
            try:
                igs.maybe_refresh(db, get_settings(), cipher, acct)
                assert acct.token is not None
                client = client_factory(cipher.decrypt(acct.token.ciphertext), acct.ig_user_id)
                res = igs.sync_account(db, acct, client)
                db.commit()
                res["activity"] = sync_activity(db, acct, client)
                q.set_setting(db, "auto_sync", {"at": utcnow().isoformat(), "ok": True, "error": None})
                db.commit()
                log.info("auto sync done: %s", res)
                return res
            except (ig.InstagramAPIError, Exception) as e:  # never crash the scheduler
                db.rollback()
                acct = igs.live_account(db)
                if acct is not None:
                    acct.last_error = str(e)[:300]
                q.set_setting(
                    db, "auto_sync", {"at": utcnow().isoformat(), "ok": False, "error": str(e)[:300]}
                )
                db.commit()
                log.warning("auto sync failed: %s", e)
                return {"error": str(e)[:300]}


def start_scheduler(sf: sessionmaker, client_factory: Callable | None = None):
    from datetime import datetime

    from apscheduler.schedulers.background import BackgroundScheduler

    sched = BackgroundScheduler(timezone="Asia/Kolkata")
    sched.add_job(remind_due_posts, "interval", minutes=10, args=[sf], id="reminders", max_instances=1)
    if client_factory is not None:
        # 06:30 IST daily, plus one catch-up run shortly after start if the last sync is older than 20h.
        sched.add_job(
            auto_sync, "cron", hour=6, minute=30, args=[sf, client_factory], id="auto_sync", max_instances=1
        )
        sched.add_job(
            auto_sync,
            "date",
            run_date=datetime.now(UTC) + timedelta(minutes=2),
            args=[sf, client_factory],
            id="auto_sync_catchup",
        )
    sched.start()
    log.info("local scheduler started")
    return sched

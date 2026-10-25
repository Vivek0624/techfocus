"""Content library, calendar, personas, experiments, approvals."""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (
    ApprovalRequest,
    AudiencePersona,
    CalendarItem,
    ContentIdea,
    Experiment,
    ExperimentObservation,
    utcnow,
)
from ..schemas import (
    ApprovalOut,
    CalendarCreate,
    CalendarOut,
    CalendarUpdate,
    ContentCreate,
    ContentOut,
    ContentUpdate,
    ExperimentIn,
    ExperimentOut,
    ExperimentUpdate,
    ObservationIn,
    Page,
    PersonaIn,
    PersonaOut,
)
from ..services import analytics as an
from ..services import queries as q

router = APIRouter()

SORTS = {
    "created": ContentIdea.created_at,
    "updated": ContentIdea.updated_at,
    "title": ContentIdea.title,
    "status": ContentIdea.status,
    "planned": ContentIdea.planned_at,
}


def _idea(db: Session, idea_id: int) -> ContentIdea:
    idea = db.get(ContentIdea, idea_id)
    if idea is None or idea.is_demo != q.use_demo(db):
        raise HTTPException(404, "content idea not found")
    return idea


@router.get("/content", response_model=Page[ContentOut])
def list_content(
    search: str | None = Query(default=None, max_length=100),
    status: str | None = None,
    pillar: str | None = None,
    sort: str = "updated",
    order: str = "desc",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
):
    stmt = select(ContentIdea).where(ContentIdea.is_demo.is_(q.use_demo(db)))
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            or_(
                ContentIdea.title.ilike(like),
                ContentIdea.recommended_hook.ilike(like),
                ContentIdea.script.ilike(like),
            )
        )
    if status:
        stmt = stmt.where(ContentIdea.status == status)
    if pillar:
        stmt = stmt.where(ContentIdea.pillar == pillar)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    col = SORTS.get(sort, ContentIdea.updated_at)
    stmt = stmt.order_by(col.asc() if order == "asc" else col.desc())
    items = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    return Page[ContentOut](
        items=[ContentOut.model_validate(i) for i in items], total=total, page=page, page_size=page_size
    )


@router.get("/content/export")
def export_content(fmt: str = Query(default="csv", pattern="^(csv|json)$"), db: Session = Depends(get_db)):
    rows = db.scalars(select(ContentIdea).where(ContentIdea.is_demo.is_(q.use_demo(db)))).all()
    data = [ContentOut.model_validate(r).model_dump(mode="json") for r in rows]
    if fmt == "json":
        return data
    buf = io.StringIO()
    cols = [
        "id",
        "title",
        "pillar",
        "audience_segment",
        "format",
        "status",
        "recommended_hook",
        "caption",
        "hashtags",
        "planned_at",
        "created_at",
    ]
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for d in data:
        w.writerow({**d, "hashtags": " ".join(d["hashtags"])})
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=content.csv"},
    )


@router.post("/content", response_model=ContentOut, status_code=201)
def create_content(body: ContentCreate, db: Session = Depends(get_db)):
    idea = ContentIdea(**body.model_dump(), is_demo=q.use_demo(db))
    db.add(idea)
    db.flush()
    return idea


@router.get("/content/{idea_id}", response_model=ContentOut)
def get_content(idea_id: int, db: Session = Depends(get_db)):
    return _idea(db, idea_id)


@router.patch("/content/{idea_id}", response_model=ContentOut)
def update_content(idea_id: int, body: ContentUpdate, db: Session = Depends(get_db)):
    idea = _idea(db, idea_id)
    data = body.model_dump(exclude_unset=True)
    if data.get("status") == "published" and not idea.published_media_id:
        # Allowed for manual posting, but recorded so analytics know it was a manual publish.
        idea.performance = {**(idea.performance or {}), "published_manually_at": utcnow().isoformat()}
    for k, v in data.items():
        setattr(idea, k, v)
    db.flush()
    return idea


@router.delete("/content/{idea_id}", status_code=204)
def delete_content(idea_id: int, db: Session = Depends(get_db)):
    db.delete(_idea(db, idea_id))


@router.post("/content/{idea_id}/clone", response_model=ContentOut, status_code=201)
def clone_content(idea_id: int, db: Session = Depends(get_db)):
    src = _idea(db, idea_id)
    data = ContentCreate.model_validate(src, from_attributes=True).model_dump()
    data.update(title=f"{src.title} (copy)"[:200], status="idea", planned_at=None)
    idea = ContentIdea(**data, is_demo=src.is_demo)
    db.add(idea)
    db.flush()
    return idea


# ---------------- calendar ----------------


@router.get("/calendar", response_model=list[CalendarOut])
def list_calendar(start: datetime | None = None, end: datetime | None = None, db: Session = Depends(get_db)):
    stmt = select(CalendarItem).where(CalendarItem.is_demo.is_(q.use_demo(db)))
    if start:
        stmt = stmt.where(CalendarItem.scheduled_at >= _to_utc(start))
    if end:
        stmt = stmt.where(CalendarItem.scheduled_at < _to_utc(end))
    return db.scalars(stmt.order_by(CalendarItem.scheduled_at)).all()


@router.post("/calendar", response_model=CalendarOut, status_code=201)
def create_calendar(body: CalendarCreate, db: Session = Depends(get_db)):
    body.scheduled_at = _to_utc(body.scheduled_at)
    item = CalendarItem(**body.model_dump(), is_demo=q.use_demo(db))
    db.add(item)
    if body.idea_id:
        idea = db.get(ContentIdea, body.idea_id)
        if idea:
            idea.planned_at = body.scheduled_at
    db.flush()
    return item


def _to_utc(dt: datetime) -> datetime:
    """Naive times are IST wall-clock; everything is stored in UTC."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=an.IST)
    return dt.astimezone(UTC)


def _cal(db: Session, item_id: int) -> CalendarItem:
    item = db.get(CalendarItem, item_id)
    if item is None or item.is_demo != q.use_demo(db):
        raise HTTPException(404, "calendar item not found")
    return item


@router.patch("/calendar/{item_id}", response_model=CalendarOut)
def update_calendar(item_id: int, body: CalendarUpdate, db: Session = Depends(get_db)):
    item = _cal(db, item_id)
    data = body.model_dump(exclude_unset=True)
    if data.get("scheduled_at"):
        data["scheduled_at"] = _to_utc(data["scheduled_at"])
    for k, v in data.items():
        setattr(item, k, v)
    db.flush()
    return item


@router.delete("/calendar/{item_id}", status_code=204)
def delete_calendar(item_id: int, db: Session = Depends(get_db)):
    item = _cal(db, item_id)
    if item.publishing_status == "published":
        raise HTTPException(409, "published items are kept for history")
    db.delete(item)


@router.get("/calendar/{item_id}/manual-checklist")
def manual_checklist(item_id: int, db: Session = Depends(get_db)):
    item = _cal(db, item_id)
    return {
        "item": item.title,
        "steps": [
            "Export the final video (9:16, 1080x1920, under 90s for widest Reels distribution).",
            "Open Instagram > + > Reel, select the video.",
            "Add a cover that reads at thumbnail size.",
            "Paste the caption from this calendar item.",
            "Post, then paste the reel link back here and mark it published.",
        ],
        "caption": item.caption,
    }


# ---------------- personas ----------------


@router.get("/personas", response_model=list[PersonaOut])
def list_personas(db: Session = Depends(get_db)):
    return db.scalars(select(AudiencePersona).where(AudiencePersona.is_demo.is_(q.use_demo(db)))).all()


@router.post("/personas", response_model=PersonaOut, status_code=201)
def create_persona(body: PersonaIn, db: Session = Depends(get_db)):
    p = AudiencePersona(**body.model_dump(), is_demo=q.use_demo(db))
    db.add(p)
    db.flush()
    return p


@router.put("/personas/{pid}", response_model=PersonaOut)
def update_persona(pid: int, body: PersonaIn, db: Session = Depends(get_db)):
    p = db.get(AudiencePersona, pid)
    if p is None:
        raise HTTPException(404, "persona not found")
    for k, v in body.model_dump().items():
        setattr(p, k, v)
    return p


@router.delete("/personas/{pid}", status_code=204)
def delete_persona(pid: int, db: Session = Depends(get_db)):
    p = db.get(AudiencePersona, pid)
    if p is None:
        raise HTTPException(404, "persona not found")
    db.delete(p)


# ---------------- experiments ----------------


def _exp_out(e: Experiment) -> ExperimentOut:
    c = [o.value for o in e.observations if o.arm == "control"]
    v = [o.value for o in e.observations if o.arm == "variant"]
    base = {k: getattr(e, k) for k in ExperimentOut.model_fields if k not in ("result", "observations")}
    return ExperimentOut(
        **base,
        result=an.evaluate_experiment(c, v, e.min_samples_per_arm),
        observations=[
            {"id": o.id, "arm": o.arm, "value": o.value, "media_ref": o.media_ref, "source": o.source}
            for o in e.observations
        ],
    )


@router.get("/experiments", response_model=list[ExperimentOut])
def list_experiments(db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Experiment)
        .where(Experiment.is_demo.is_(q.use_demo(db)))
        .order_by(Experiment.created_at.desc())
    )
    return [_exp_out(e) for e in rows]


@router.post("/experiments", response_model=ExperimentOut, status_code=201)
def create_experiment(body: ExperimentIn, db: Session = Depends(get_db)):
    e = Experiment(**body.model_dump(), is_demo=q.use_demo(db))
    db.add(e)
    db.flush()
    return _exp_out(e)


@router.patch("/experiments/{eid}", response_model=ExperimentOut)
def update_experiment(eid: int, body: ExperimentUpdate, db: Session = Depends(get_db)):
    e = db.get(Experiment, eid)
    if e is None:
        raise HTTPException(404, "experiment not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(e, k, v)
    db.flush()
    return _exp_out(e)


@router.post("/experiments/{eid}/observations", response_model=ExperimentOut, status_code=201)
def add_observation(eid: int, body: ObservationIn, db: Session = Depends(get_db)):
    e = db.get(Experiment, eid)
    if e is None:
        raise HTTPException(404, "experiment not found")
    db.add(ExperimentObservation(experiment_id=eid, **body.model_dump()))
    if e.status == "planned":
        e.status = "running"
    db.flush()
    db.refresh(e)
    return _exp_out(e)


@router.delete("/experiments/{eid}", status_code=204)
def delete_experiment(eid: int, db: Session = Depends(get_db)):
    e = db.get(Experiment, eid)
    if e is None:
        raise HTTPException(404, "experiment not found")
    db.delete(e)


# ---------------- approvals ----------------


@router.get("/approvals", response_model=list[ApprovalOut])
def list_approvals(status: str | None = None, db: Session = Depends(get_db)):
    stmt = select(ApprovalRequest)
    if status:
        stmt = stmt.where(ApprovalRequest.status == status)
    return db.scalars(stmt.order_by(ApprovalRequest.created_at.desc()).limit(100)).all()


@router.post("/approvals/{aid}/decision", response_model=ApprovalOut)
def decide(aid: int, approve: bool, db: Session = Depends(get_db)):
    ap = db.get(ApprovalRequest, aid)
    if ap is None:
        raise HTTPException(404, "approval not found")
    if ap.status != "pending":
        raise HTTPException(409, f"already {ap.status}")
    ap.status, ap.decided_at = ("approved" if approve else "rejected"), utcnow()
    if ap.target_type == "calendar_item":
        item = db.get(CalendarItem, ap.target_id)
        if item:
            item.approval_status = ap.status
    db.flush()
    return ap

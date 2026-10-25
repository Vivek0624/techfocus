"""Synthetic demo data. Everything here has is_demo=True / source='demo' and an obviously fake account.
reset_demo() deletes demo rows only; real account records are untouched."""

from __future__ import annotations

import random
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .agents.registry import AGENTS
from .models import (
    SOURCE_DEMO,
    AccountSnapshot,
    AgentDefinition,
    AgentRun,
    AudiencePersona,
    CalendarItem,
    ContentIdea,
    DailyTask,
    Experiment,
    ExperimentObservation,
    GrowthPlan,
    InstagramAccount,
    LearningRecord,
    Media,
    MediaSnapshot,
)
from .services import analytics as an
from .services.creator import classify_hook
from .services.queries import set_setting


def _utc(dt: datetime) -> datetime:
    return dt.astimezone(UTC)


DEMO_USERNAME = "demo_techfocus (SYNTHETIC)"

# (title, category, format, seconds, spoken hook, views multiple, shares per 1k reach). Synthetic.
REELS = [
    (
        "How to speak confidently in interviews",
        "skills",
        "talking_head",
        45,
        "Most people freeze in interviews for one reason.",
        90,
        14,
    ),
    (
        "Your ₹20 chai order is an API call",
        "tech_concepts",
        "motion_graphics",
        30,
        "Your ₹20 chai order already explains APIs.",
        1.4,
        9,
    ),
    (
        "Stop memorising AWS services",
        "tech_concepts",
        "talking_head",
        35,
        "Stop memorising AWS services.",
        1.2,
        6,
    ),
    (
        "10 AI tools for students",
        "ai",
        "screen_recording",
        50,
        "10 AI tools every student should know.",
        1.1,
        2,
    ),
    (
        "How do some people stay one step ahead?",
        "relatable_learning",
        "talking_head",
        40,
        "Why do some people always seem one step ahead?",
        0.9,
        5,
    ),
    (
        "REST vs GraphQL in 30 seconds",
        "tech_concepts",
        "motion_graphics",
        30,
        "REST vs GraphQL in 30 seconds.",
        1.3,
        8,
    ),
    (
        "5 ChatGPT prompts for coders",
        "ai",
        "screen_recording",
        55,
        "5 ChatGPT prompts I use every day.",
        0.8,
        2,
    ),
    (
        "Why doesn't UPI crash at 8pm?",
        "tech_concepts",
        "motion_graphics",
        35,
        "Crores of people pay on UPI at 8pm. Why doesn't it crash?",
        1.6,
        10,
    ),
    (
        "Your degree doesn't decide your tech career",
        "career",
        "talking_head",
        40,
        "Your degree does not decide your tech career.",
        12,
        13,
    ),
    (
        "3 VS Code shortcuts I use daily",
        "skills",
        "screen_recording",
        25,
        "3 VS Code shortcuts I use daily.",
        0.7,
        3,
    ),
    (
        "Every error taught you something",
        "relatable_learning",
        "talking_head",
        20,
        "Every error before it worked taught you something.",
        1.0,
        6,
    ),
    (
        "AI tools that replaced my workflow",
        "ai",
        "screen_recording",
        60,
        "These AI tools replaced half my workflow.",
        0.6,
        2,
    ),
    (
        "Prompt vs no prompt: same task",
        "ai",
        "motion_graphics",
        30,
        "Same task. One prompt. Two very different answers.",
        1.2,
        5,
    ),
    (
        "Explain your project in 60 seconds",
        "career",
        "talking_head",
        60,
        "Nobody tells you how to explain your own project.",
        2.1,
        11,
    ),
]


# Feed posts (carousels / images): Instagram reports follows and profile visits for these, not for Reels.
# (title, category, media_type, views multiple, shares per 1k, follows per 1k reach, profile visits per 1k). Synthetic.
FEED_POSTS = [
    ("5 interview questions freshers get wrong (carousel)", "career", "CAROUSEL_ALBUM", 1.3, 12, 6, 31),
    ("API vs SDK vs library, one slide each", "tech_concepts", "CAROUSEL_ALBUM", 1.0, 8, 4, 22),
    ("My desk setup for learning AWS", "relatable_learning", "IMAGE", 0.6, 1, 1, 9),
]
# Audience tags the creator set by hand (the rest are inferred from topic + wording).
DEMO_AUDIENCE = {"5 ChatGPT prompts for coders": "developers", "10 AI tools for students": "students"}


def seed_agents(db: Session) -> None:
    for a in AGENTS.values():
        row = db.get(AgentDefinition, a.id)
        if row is None:
            db.add(AgentDefinition(id=a.id, name=a.name, responsibility=a.responsibility, tools=a.tools))
        else:
            row.name, row.responsibility, row.tools = a.name, a.responsibility, a.tools
    db.flush()


def seed_demo(db: Session, today: date | None = None) -> None:
    seed_demo_interests(db, today)
    if db.scalar(select(InstagramAccount).where(InstagramAccount.is_demo.is_(True))):
        return
    today = today or date.today()
    rng = random.Random(42)
    acct = InstagramAccount(
        ig_user_id="demo-0001",
        username=DEMO_USERNAME,
        account_type="MEDIA_CREATOR",
        is_demo=True,
        connected=False,
        granted_scopes=[],
    )
    db.add(acct)
    db.flush()

    followers = 310
    start = today - timedelta(days=45)
    for i in range(46):
        d = start + timedelta(days=i)
        reach = rng.randint(600, 2500) + (40000 if i == 30 else 0)
        follows = max(0, int(reach * rng.uniform(0.002, 0.006)))
        unfollows = rng.randint(0, 3)
        followers += follows - unfollows
        db.add(
            AccountSnapshot(
                account_id=acct.id,
                snapshot_date=d,
                source=SOURCE_DEMO,
                followers=followers,
                follows=follows,
                unfollows=unfollows,
                reach=reach,
                views=int(reach * rng.uniform(1.3, 2.0)),
                accounts_engaged=int(reach * 0.04),
                total_interactions=int(reach * 0.06),
                likes=int(reach * 0.045),
                comments=int(reach * 0.003),
                shares=int(reach * 0.006),
                saves=int(reach * 0.007),
                profile_links_taps=rng.randint(0, 4),
            )
        )

    for i, (title, pillar, fmt, secs, hook_text, mult, share_rate) in enumerate(REELS):
        pub = _utc(
            datetime.combine(
                today - timedelta(days=3 * i + 1), time(rng.choice([13, 19, 20, 21]), 0), tzinfo=an.IST
            )
        )
        views = int(1700 * mult * rng.uniform(0.9, 1.1))
        m = Media(
            account_id=acct.id,
            ig_media_id=f"demo-media-{i:03d}",
            media_type="VIDEO",
            media_product_type="REELS",
            caption=title,
            permalink=None,
            published_at=pub,
            source=SOURCE_DEMO,
            pillar=pillar,
            hook_style=classify_hook(hook_text),
            hook_text=hook_text,
            format_style=fmt,
            length_seconds=secs,
            audience=DEMO_AUDIENCE.get(title),
        )
        db.add(m)
        db.flush()
        reach = int(views * 0.7)
        db.add(
            MediaSnapshot(
                media_id=m.id,
                snapshot_date=today,
                source=SOURCE_DEMO,
                views=views,
                reach=reach,
                likes=int(reach * 0.05),
                comments=int(reach * 0.004),
                shares=int(reach * share_rate / 1000),
                saved=int(reach * 0.01),
                total_interactions=int(reach * 0.072),
                avg_watch_time_ms=int(secs * 1000 * rng.uniform(0.25, 0.55)),
                # Reposts aren't returned for every post; missing stays None, never 0.
                reposts=int(reach * share_rate / 1000 * 0.2) if i % 3 != 2 else None,
            )
        )

    for i, (title, pillar, mtype, mult, share_rate, follow_rate, visit_rate) in enumerate(FEED_POSTS):
        pub = _utc(datetime.combine(today - timedelta(days=3 * i + 2), time(13, 0), tzinfo=an.IST))
        views = int(1700 * mult * rng.uniform(0.9, 1.1))
        m = Media(
            account_id=acct.id,
            ig_media_id=f"demo-feed-{i:03d}",
            media_type=mtype,
            media_product_type="FEED",
            caption=title,
            permalink=None,
            published_at=pub,
            source=SOURCE_DEMO,
            pillar=pillar,
            hook_text=title.split(" (")[0],
            hook_style=classify_hook(title),
            format_style="carousel" if mtype == "CAROUSEL_ALBUM" else "mixed",
        )
        db.add(m)
        db.flush()
        reach = int(views * 0.75)
        db.add(
            MediaSnapshot(
                media_id=m.id,
                snapshot_date=today,
                source=SOURCE_DEMO,
                views=views,
                reach=reach,
                likes=int(reach * 0.06),
                comments=int(reach * 0.005),
                shares=int(reach * share_rate / 1000),
                saved=int(reach * 0.025),
                total_interactions=int(reach * 0.09),
                follows=int(reach * follow_rate / 1000),
                profile_visits=int(reach * visit_rate / 1000),
                profile_activity=int(reach * visit_rate / 1000 * 0.3),
                reposts=int(reach * share_rate / 1000 * 0.2) if i != 2 else None,
            )
        )

    ideas = [
        (
            "Your English isn't why you fail interviews",
            "career",
            "Interview candidates",
            "ready",
        ),
        (
            "Crores pay on UPI at 8pm. Why doesn't it crash?",
            "tech_concepts",
            "Working engineers",
            "recording",
        ),
        (
            "ChatGPT vs a chai stall: who explains APIs better?",
            "tech_concepts",
            "Non-technical learners",
            "script",
        ),
        ("How Instagram's feed learns what you like", "tech_concepts", "College students", "idea"),
        ("Every developer has pushed to main on a Friday", "relatable_learning", "Working engineers", "idea"),
        ("Manual vs AI: writing a cover letter", "ai", "College students", "editing"),
        ("Explain your project like a story", "career", "Interview candidates", "idea"),
    ]
    idea_rows = []
    for t, p, seg, st in ideas:
        idea = ContentIdea(
            title=t,
            pillar=p,
            audience_segment=seg,
            status=st,
            is_demo=True,
            format="screen_recording" if t.startswith("Manual vs AI") else "talking_head",
            recommended_hook=t,
            hook_options=[t],
            effort="medium",
            duration_seconds=30,
            hypothesis="Follow-up to the communication outlier (demo).",
            caption=f"{t}\n\nSave this. (demo caption)",
        )
        db.add(idea)
        idea_rows.append(idea)
    db.flush()
    for k, idea in enumerate(idea_rows[:3]):
        db.add(
            CalendarItem(
                idea_id=idea.id,
                title=idea.title,
                format="talking_head",
                scheduled_at=_utc(
                    datetime.combine(today + timedelta(days=k + 1), time(19, 0), tzinfo=an.IST)
                ),
                caption=idea.caption,
                production_status=idea.status,
                is_demo=True,
            )
        )

    personas = [
        (
            "College students",
            "inferred",
            ["first job", "skills"],
            ["don't know what to learn"],
            ["skills beyond marks"],
        ),
        (
            "Interview candidates",
            "inferred",
            ["interviews", "communication"],
            ["freeze explaining projects"],
            ["communication for developers"],
        ),
        ("Beginner developers", "hypothesis", ["coding basics"], ["tutorial hell"], ["build, don't watch"]),
        ("Working software engineers", "hypothesis", ["system design", "AI"], ["no time"], ["AI workflows"]),
        (
            "Non-technical learners",
            "hypothesis",
            ["AI tools"],
            ["tech feels intimidating"],
            ["everyday Indian examples"],
        ),
        ("AI tool explorers", "hypothesis", ["prompts"], ["generic outputs"], ["prompt before/after"]),
        ("Aspiring tech creators", "hypothesis", ["content"], ["no audience"], ["behind the scenes"]),
    ]
    for n, lvl, i_, p_, a_ in personas:
        db.add(
            AudiencePersona(name=n, evidence_level=lvl, interests=i_, problems=p_, angles=a_, is_demo=True)
        )

    e1 = Experiment(
        name="Identity-reframe vs explainer hook",
        hypothesis="Reframe openers raise views",
        variable="hook_style",
        control="explainer opener",
        variant="identity-reframe opener",
        status="running",
        is_demo=True,
    )
    e2 = Experiment(
        name="13:00 vs 19:00 IST",
        hypothesis="Evening posts reach more",
        variable="publish_window",
        control="13:00 IST",
        variant="19:00 IST",
        status="planned",
        is_demo=True,
    )
    db.add_all([e1, e2])
    db.flush()
    for v in (1200, 1900, 1500, 1100):
        db.add(ExperimentObservation(experiment_id=e1.id, arm="control", value=v, source=SOURCE_DEMO))
    for v in (2600, 4100, 2200):
        db.add(ExperimentObservation(experiment_id=e1.id, arm="variant", value=v, source=SOURCE_DEMO))

    for t, imp, mins in [
        ("Review yesterday's reel vs your median", 2, 10),
        ("Record 'Your English isn't why you fail interviews'", 3, 60),
        ("Finish caption for the UPI reel", 2, 15),
        ("Reply to genuine questions in comments", 2, 20),
    ]:
        db.add(
            DailyTask(
                task_date=today,
                title=t,
                impact=imp,
                effort_minutes=mins,
                priority=imp * 10 - mins / 10,
                is_demo=True,
                reason="demo task",
            )
        )
    run = AgentRun(
        agent_id="analytics",
        mode="mock",
        status="succeeded",
        input={"days": 30},
        input_summary="days=30",
        output_summary="Demo: communication reel ran ~90x median.",
        output={},
        duration_ms=180,
        is_demo=True,
        started_at=_utc(datetime.combine(today, time(8, 0), tzinfo=an.IST)),
        finished_at=_utc(datetime.combine(today, time(8, 0, 1), tzinfo=an.IST)),
    )
    fail = AgentRun(
        agent_id="content_research",
        mode="mock",
        status="failed",
        input={"topic": "Kafka"},
        input_summary="topic=Kafka",
        error="Simulated failure: research provider not configured.",
        duration_ms=40,
        is_demo=True,
    )
    db.add_all([run, fail])
    db.add(
        GrowthPlan(
            period="daily",
            plan_date=today,
            is_demo=True,
            content={
                "bottleneck": "conversion (demo)",
                "next_action": "Pin the top reel and post its follow-up",
            },
        )
    )
    db.add(
        LearningRecord(
            kind="pattern",
            statement="Communication reels outperform (1 outlier - not a rule)",
            sample_size=1,
            confidence="low",
            decision="test_more",
            is_demo=True,
        )
    )
    _seed_activity(db, acct.id, today, rng)
    set_setting(
        db,
        "demo_target",
        {
            "target": 10000,
            "days": 30,
            "start_followers": 339,
            "start_date": (today - timedelta(days=15)).isoformat(),
        },
    )
    db.flush()


DEMO_COMMENTS = [
    (0, "rahul.codes", "How do I practise speaking English for interviews if no one around me speaks it?"),
    (0, "priya_dev", "Please make a part 2 on how to answer 'tell me about yourself'"),
    (0, "ankit_99", "This is so helpful, thank you bhai 🔥"),
    (0, "sneha.learns", "What should I say when I don't know the answer to a technical question?"),
    (0, "growth_hacks_pro", "DM us for promotion, 10k followers guaranteed"),
    (1, "techie_tanvi", "Can you explain REST vs GraphQL like this too?"),
    (1, "vikram.s", "Finally understood APIs. Amazing analogy"),
    (7, "kunal_k", "Why does UPI fail sometimes then?"),
    (7, "meera.codes", "Make a video on how Paytm/PhonePe handle refunds"),
    (8, "student_aditi", "I'm from a non-CS background, which role should I target first?"),
    (8, "harsh.dev", "Not true for all companies, many still filter on degree"),
    (8, "follow4follow_x", "Nice! Follow back? Check my page"),
    (13, "devraj", "How long should my project explanation be in an interview?"),
    (5, "nisha_ai", "Kya ye roadmap freshers ke liye bhi kaam karega?"),
    (7, "rahul.codes", "How do UPI refunds actually work? Mine took 5 days"),
    (1, "pooja_tech", "Please explain refunds on PhonePe, always confusing"),
    (8, "bca.student", "Non-CS here, which role should I start with? Testing or frontend?"),
    (2, "freshers.hub", "Which role is best for freshers from a non-CS background?"),
    (4, "arjun.ai", "Can you make a video on how to start learning system design?"),
    (11, "kavya.dev", "System design for freshers kaise start kare?"),
]


def _seed_activity(db: Session, account_id: int, today: date, rng: random.Random) -> None:
    from .models import AudienceSnapshot, Comment, Mention
    from .services.activity import classify, draft_reply

    medias = db.scalars(
        select(Media)
        .where(Media.account_id == account_id, Media.media_product_type == "REELS")
        .order_by(Media.published_at.desc())
    ).all()
    for k, (mi, user, text) in enumerate(DEMO_COMMENTS):
        m = medias[mi % len(medias)]
        intent = classify(text)
        db.add(
            Comment(
                ig_comment_id=f"demo-c-{k}",
                media_id=m.id,
                username=user,
                text=text,
                intent=intent,
                draft_reply=draft_reply(text, intent, user),
                source=SOURCE_DEMO,
                is_demo=True,
                like_count=rng.randint(0, 40),
                commented_at=(m.published_at or datetime.now(UTC)) + timedelta(hours=k + 1),
            )
        )
    for k, (user, cap) in enumerate(
        [
            ("pune.tech.meetup", "Thanks @vivek_techfocus for the AWS session!"),
            ("career.with.riya", "Great explanation by @vivek_techfocus on interview prep"),
            ("codewithanush", "Collab reel with @vivek_techfocus on APIs"),
        ]
    ):
        db.add(
            Mention(
                ig_media_id=f"demo-mention-{k}",
                username=user,
                caption=cap,
                permalink=None,
                posted_at=_utc(
                    datetime.combine(today - timedelta(days=2 + 5 * k), time(18, 0), tzinfo=an.IST)
                ),
                source=SOURCE_DEMO,
                is_demo=True,
            )
        )
    audience = {
        "followers_age": {"18-24": 172, "25-34": 131, "35-44": 22, "45-54": 6, "13-17": 8},
        "followers_gender": {"M": 241, "F": 93, "U": 5},
        "followers_city": {
            "Pune, Maharashtra": 64,
            "Bengaluru, Karnataka": 51,
            "Hyderabad, Telangana": 38,
            "Mumbai, Maharashtra": 29,
            "Chennai, Tamil Nadu": 17,
            "Delhi, Delhi": 15,
        },
        "followers_country": {"IN": 309, "US": 11, "AE": 7, "GB": 4},
        "online_hours": {
            str(h): int(
                40 * (0.25 + (h in (13, 14)) * 0.5 + (19 <= h <= 22) * 0.9 + (h >= 23 or h <= 6) * -0.2)
            )
            for h in range(24)
        },
    }
    for kind, data in audience.items():
        db.add(
            AudienceSnapshot(
                account_id=account_id, snapshot_date=today, kind=kind, data=data, source=SOURCE_DEMO
            )
        )


DEMO_INTERESTS = [
    # (source, creator, collection, note)
    ("saved", "techwithtim_demo", "AI tools", None),
    ("saved", "aiexplained_demo", "AI tools", None),
    ("saved", "aiexplained_demo", "AI tools", None),
    ("saved", "promptcraft_demo", "AI tools", None),
    ("saved", "careercoach_demo", "Interview prep", None),
    ("saved", "careercoach_demo", "Interview prep", None),
    ("saved", "resumefix_demo", "Interview prep", None),
    ("saved", "codehumor_demo", "Funny", None),
    ("saved", "upi_explained_demo", None, None),
    ("liked", "aiexplained_demo", None, None),
    ("liked", "aiexplained_demo", None, None),
    ("liked", "devmemes_demo", None, None),
    ("liked", "careercoach_demo", None, None),
    ("liked", "cloudsimple_demo", None, None),
    ("following", "aiexplained_demo", None, None),
    ("following", "careercoach_demo", None, None),
    ("topic", None, "Technology", None),
    ("topic", None, "Artificial intelligence", None),
    ("topic", None, "Careers", None),
    ("manual", "aiexplained_demo", None, "Loved how he showed ChatGPT writing a resume in 30 seconds"),
    ("manual", "careercoach_demo", None, "Simple interview tip, great hook in the first 2 seconds"),
]


def seed_demo_interests(db: Session, today: date | None = None) -> None:
    """Synthetic saved/liked items for demo mode only (is_demo=True). Never touches the live partition."""
    from .models import InterestItem

    if db.scalar(select(InterestItem.id).where(InterestItem.is_demo.is_(True)).limit(1)):
        return
    from sqlalchemy.exc import IntegrityError

    today = today or date.today()
    try:
        with db.begin_nested():  # the http and https API processes may seed at the same moment
            for n, (src, creator, coll, note) in enumerate(DEMO_INTERESTS):
                when = datetime.combine(today - timedelta(days=3 + n * 9), time(20, 0), tzinfo=UTC)
                db.add(
                    InterestItem(
                        source=src,
                        creator=creator,
                        collection=coll,
                        note=note,
                        url=f"https://www.instagram.com/reel/DEMO{n:03d}/"
                        if src in ("saved", "liked", "manual")
                        else None,
                        happened_at=when,
                        origin="demo",
                        dedupe_key=f"demo|{n}",
                        is_demo=True,
                    )
                )
            db.flush()
    except IntegrityError:
        pass


def reset_demo(db: Session) -> None:
    from .models import InterestItem, Recommendation

    db.execute(delete(InterestItem).where(InterestItem.is_demo.is_(True)))
    db.execute(delete(Recommendation).where(Recommendation.is_demo.is_(True)))
    demo_acct_ids = list(db.scalars(select(InstagramAccount.id).where(InstagramAccount.is_demo.is_(True))))
    for model in (CalendarItem, DailyTask, GrowthPlan, LearningRecord, AudiencePersona, Experiment, AgentRun):
        db.execute(delete(model).where(model.is_demo.is_(True)))
    from .models import Comment, Mention

    db.execute(delete(Comment).where(Comment.is_demo.is_(True)))
    db.execute(delete(Mention).where(Mention.is_demo.is_(True)))
    db.execute(delete(ContentIdea).where(ContentIdea.is_demo.is_(True)))
    if demo_acct_ids:
        db.execute(delete(InstagramAccount).where(InstagramAccount.id.in_(demo_acct_ids)))
    db.flush()
    seed_demo(db)

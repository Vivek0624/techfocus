from datetime import UTC, date, datetime

from app.services import analytics as an


def test_growth_formulas():
    assert an.net_growth(100, 130) == 30
    assert an.pct_growth(100, 130) == 30.0
    assert an.net_growth(None, 130) is None
    assert an.pct_growth(0, 10) is None


def test_engagement_requires_all_fields():
    assert (
        an.engagement_rate_by_reach([{"likes": 10, "comments": 0, "shares": 0, "saved": 0, "reach": 100}])
        == 10.0
    )
    assert (
        an.engagement_rate_by_reach([{"likes": 10, "comments": None, "shares": 0, "saved": 0, "reach": 100}])
        is None
    )
    assert (
        an.engagement_rate_by_reach([{"likes": 10, "comments": 1, "shares": 0, "saved": 0, "reach": 0}])
        is None
    )


def test_follows_per_1k():
    assert an.follows_per_1k_reach([{"follows": 5, "reach": 1000}, {"follows": 5, "reach": 1000}]) == 5.0
    assert an.follows_per_1k_reach([{"follows": None, "reach": 1000}]) is None


def test_outlier_excludes_self_from_baseline():
    posts = [{"views": v} for v in (100, 100, 100, 100, 10000)]
    out = an.outlier_multiples(posts)
    assert out[-1]["multiple"] == 100.0
    assert out[0]["multiple"] == 1.0
    assert an.outlier_multiples([{"views": 1}, {"views": 2}])[0]["multiple"] is None


def test_target_progress():
    tp = an.target_progress(339, 10000, date(2026, 10, 1), 30, 600, date(2026, 10, 16))
    assert tp.days_remaining == 15 and tp.remaining == 9400
    assert tp.required_per_day == round(9400 / 15, 1)
    assert tp.actual_per_day == round(261 / 15, 1)
    assert tp.on_pace is False
    late = an.target_progress(339, 10000, date(2026, 10, 1), 30, 600, date(2026, 12, 1))
    assert late.days_remaining == 1  # never divides by zero
    unknown = an.target_progress(339, 10000, date(2026, 10, 1), 30, None, date(2026, 10, 16))
    assert unknown.required_per_day is None


def test_experiment_eval():
    r = an.evaluate_experiment([1, 2], [3, 4], 3)
    assert r["status"] == "insufficient_data"
    r = an.evaluate_experiment([100, 110, 105, 98, 102], [300, 310, 290, 305, 295], 3)
    assert r["confidence"] == "medium" and r["p_value"] < 0.05
    r = an.evaluate_experiment([100, 300, 200], [110, 290, 210], 3)
    assert r["confidence"] == "none"


def test_best_time_insufficient():
    posts = [{"views": 100, "published_at": datetime(2026, 10, i, 14, tzinfo=UTC)} for i in range(1, 4)]
    assert an.best_time_analysis(posts)["status"] == "insufficient_data"


def test_window_of_ist():
    assert an.window_of(datetime(2026, 10, 1, 14, 0, tzinfo=UTC)) == "18-22"  # 19:30 IST
    assert an.window_of(datetime(2026, 10, 1, 20, 0, tzinfo=UTC)) == "22-06"  # 01:30 IST

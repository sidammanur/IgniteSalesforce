from pathlib import Path

import pytest

from leadrouter.cleaner import Lead, load_leads
from leadrouter.scoring import priority, score_lead, score_leads

DATA = Path(__file__).resolve().parent.parent / "data"


def lead(size=500, activity=None, vertical=None, vip=False, lead_id="L-1"):
    return Lead(lead_id=lead_id, company="Acme", regions=frozenset({"Europe"}), language="English",
                vertical=vertical, size=size, activity=activity, vip=vip)


def test_vip_is_always_100_and_critical():
    # even a tiny company with no activity is Critical if it's a VIP
    vip = lead(size=5, activity=None, vertical="Retail", vip=True)
    assert score_lead(vip) == 100
    assert priority(score_lead(vip)) == "Critical"


@pytest.mark.parametrize("size, points", [
    (None, 20),   # missing size -> fallback
    (1, 0), (99, 0),
    (100, 30), (999, 30),
    (1000, 50), (50_000, 50),
])
def test_company_size_points(size, points):
    assert score_lead(lead(size=size)) == points


@pytest.mark.parametrize("activity, points", [
    ("Requested Live Demo", 35), ("Contact Sales", 35), ("Attended Webinar", 25),
    ("Downloaded Whitepaper", 15), ("Visited Pricing Page", 5),
    ("Started Free Trial", 0),  # recorded but not on the cheat sheet
    (None, 0),                  # missing
])
def test_activity_points(activity, points):
    assert score_lead(lead(size=1, activity=activity)) == points


@pytest.mark.parametrize("vertical, points", [
    ("Technology", 20), ("Healthcare", 15), ("Finance", 15),
    ("Manufacturing", 0), ("Retail", 0), (None, 0),
])
def test_industry_points(vertical, points):
    assert score_lead(lead(size=1, vertical=vertical)) == points


def test_max_non_vip_score_is_capped_at_100():
    best = lead(size=5000, activity="Requested Live Demo", vertical="Technology")
    assert score_lead(best) == 100  # 50 + 35 + 20 = 105, capped


def test_vip_ranks_above_a_non_vip_with_the_same_score():
    best = lead(lead_id="best", size=5000, activity="Requested Live Demo", vertical="Technology")
    vip = lead(lead_id="vip", size=1, vip=True)
    assert [l.lead_id for l in score_leads([best, vip])] == ["vip", "best"]


@pytest.mark.parametrize("score, tier", [
    (0, "Low"), (39, "Low"),
    (40, "Medium"), (69, "Medium"),
    (70, "High"), (89, "High"),
    (90, "Critical"), (100, "Critical"),
])
def test_tier_boundaries(score, tier):
    assert priority(score) == tier


def test_lead_missing_everything_still_gets_scored():
    empty = lead(size=None, activity=None, vertical=None)
    assert score_lead(empty) == 20
    assert priority(score_lead(empty)) == "Low"


def test_score_leads_fills_in_fields_and_sorts_highest_first():
    leads = [
        lead(lead_id="low", size=1),
        lead(lead_id="vip", size=1, vip=True),
        lead(lead_id="high", size=5000, activity="Attended Webinar"),
    ]
    ranked = score_leads(leads)
    assert [l.lead_id for l in ranked] == ["vip", "high", "low"]
    assert [l.priority for l in ranked] == ["Critical", "High", "Low"]


def test_score_leads_with_no_leads():
    assert score_leads([]) == []


def test_scale_data_tiers():
    leads = score_leads(load_leads(DATA / "leads_scale.csv"))
    assert len(leads) == 50_000
    assert all(l.priority == "Critical" for l in leads if l.vip)
    # demo requests must actually score points (the old 'Requested Demo' typo gave them 0)
    assert all(l.score >= 35 for l in leads if l.activity == "Requested Live Demo")
    scores = [l.score for l in leads]
    assert scores == sorted(scores, reverse=True)

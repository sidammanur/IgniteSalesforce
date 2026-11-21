import time
from collections import Counter
from pathlib import Path

from leadrouter.cleaner import Lead, Rep, load_leads, load_reps
from leadrouter.routing import manager_review, route_leads
from leadrouter.scoring import score_leads

DATA = Path(__file__).resolve().parent.parent / "data"


def lead(lead_id="L-1", priority="Medium", score=50, regions=("Europe",), language="English",
         vertical="Technology", vip=False):
    return Lead(lead_id=lead_id, company="Acme", regions=frozenset(regions), language=language,
                vertical=vertical, size=500, activity=None, vip=vip, score=score, priority=priority)


def rep(rep_id="R-1", seniority="Senior", max_capacity=5, regions=("Europe",), language="English",
        expertise="Technology"):
    return Rep(rep_id=rep_id, name=rep_id, regions=frozenset(regions), language=language,
               expertise=expertise, seniority=seniority, current=0, max_capacity=max_capacity)


def critical(lead_id="C-1", **kwargs):
    return lead(lead_id=lead_id, priority="Critical", score=95, **kwargs)


def test_lead_only_goes_to_a_rep_that_matches_everything():
    reps = [rep("wrong-region", regions=("Asia-Pacific",)), rep("wrong-language", language="German"),
            rep("wrong-industry", expertise="Retail"), rep("match")]
    route_leads([lead()], reps)
    assert [r.rep_id for r in reps if r.current] == ["match"]


def test_no_matching_rep_goes_to_manager_review():
    [result] = route_leads([lead(vertical="Retail")], [rep()])
    assert result.assigned_to is None
    assert result.review_reason == "No rep matches region, language and industry"


def test_missing_region_or_language_goes_to_manager_review():
    leads = route_leads([lead("no-region", regions=()), lead("no-lang", language=None)], [rep()])
    assert all(l.review_reason == "Missing region or language" for l in leads)


def test_unknown_industry_lead_goes_to_a_generalist_rep():
    [result] = route_leads([lead(vertical=None)], [rep("specialist"), rep("generalist", expertise=None)])
    assert result.assigned_to == "generalist"


def test_multi_region_lead_can_match_either_region():
    [result] = route_leads([lead(regions=("North America", "Asia-Pacific"))],
                           [rep(regions=("Asia-Pacific",))])
    assert result.assigned_to == "R-1"


def test_critical_never_goes_to_a_junior():
    [result] = route_leads([critical()], [rep("junior", seniority="Junior")])
    assert result.assigned_to is None
    assert result.review_reason == "Only Junior reps match (Critical needs a Senior or Manager)"


def test_critical_overflow_when_seniors_and_managers_are_full():
    [result] = route_leads([critical()], [rep(max_capacity=0), rep("mgr", seniority="Manager", max_capacity=0),
                                          rep("junior", seniority="Junior")])
    assert result.review_reason == "All matching reps are full"


def test_critical_prefers_senior_then_manager_when_seniors_are_full():
    reps = [rep("mgr", seniority="Manager"), rep("sr", seniority="Senior", max_capacity=1)]
    leads = route_leads([critical("C-1"), critical("C-2")], reps)
    assert [l.assigned_to for l in leads] == ["sr", "mgr"]


def test_normal_leads_skip_managers():
    [result] = route_leads([lead()], [rep("mgr", seniority="Manager")])
    assert result.assigned_to is None
    assert result.review_reason == "Only Managers match (kept free for Critical leads)"


def test_critical_leads_are_routed_before_lower_ones():
    # one Senior slot: the Critical lead must get it even though it's listed last
    leads = route_leads([lead("low", score=10, priority="Low"), critical("crit")],
                        [rep(max_capacity=1)])
    assert {l.lead_id: l.assigned_to for l in leads} == {"crit": "R-1", "low": None}


def test_identical_reps_take_turns():
    reps = [rep("A"), rep("B"), rep("C")]
    leads = route_leads([lead(f"L-{i}") for i in range(6)], reps)
    assert [l.assigned_to for l in leads] == ["A", "B", "C", "A", "B", "C"]


def test_least_busy_rep_by_percentage_goes_first():
    small, big = rep("small", max_capacity=2), rep("big", max_capacity=10)
    small.current = 1  # 50% used
    big.current = 2    # 20% used
    [result] = route_leads([lead()], [small, big])
    assert result.assigned_to == "big"


def test_capacity_is_never_exceeded_and_overflow_is_kept():
    reps = [rep("A", max_capacity=2), rep("B", max_capacity=1)]
    leads = route_leads([lead(f"L-{i}") for i in range(5)], reps)
    assert (reps[0].current, reps[1].current) == (2, 1)
    overflow = manager_review(leads)
    assert len(overflow) == 2
    assert all(l.review_reason == "All matching reps are full" for l in overflow)


def test_rep_with_zero_capacity_gets_nothing():
    [result] = route_leads([lead()], [rep(max_capacity=0)])
    assert result.assigned_to is None


def test_no_leads_or_no_reps():
    assert route_leads([], [rep()]) == []
    [result] = route_leads([lead()], [])
    assert result.assigned_to is None


def run(leads_file, reps_file):
    reps = load_reps(DATA / reps_file)
    leads = route_leads(score_leads(load_leads(DATA / leads_file)), reps)
    return leads, reps


def check_rules(leads, reps):
    by_id = {r.rep_id: r for r in reps}
    for l in leads:
        assert (l.assigned_to is None) != (l.review_reason == "")  # assigned XOR has a reason
        if l.priority == "Critical" and l.assigned_to:
            assert by_id[l.assigned_to].seniority != "Junior"
    assert all(r.current <= r.max_capacity for r in reps)
    assigned = Counter(l.assigned_to for l in leads if l.assigned_to)
    assert all(assigned[r.rep_id] == r.current for r in reps)


def test_sample_data_end_to_end():
    leads, reps = run("leads_sample.csv", "reps_sample.csv")
    assert len(leads) == 100
    check_rules(leads, reps)


def test_scale_data_end_to_end_is_fast_and_follows_the_rules():
    start = time.perf_counter()
    leads, reps = run("leads_scale.csv", "reps_scale.csv")
    assert time.perf_counter() - start < 5
    assert len(leads) == 50_000
    check_rules(leads, reps)

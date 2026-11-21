from leadrouter.pipeline import run
from leadrouter.suggest import START_WEIGHTS, Suggester
from test_routing import critical, lead, rep


def test_suggests_a_rep_from_another_industry_when_needed():
    s = Suggester([rep("retail", expertise="Retail")])
    assert s.best_rep(lead(vertical="Technology")).rep_id == "retail"


def test_region_and_language_still_have_to_match():
    s = Suggester([rep("asia", regions=("Asia-Pacific",)), rep("german", language="German")])
    assert s.best_rep(lead()) is None


def test_prefers_same_industry_over_more_free_room():
    s = Suggester([rep("other", expertise="Retail", max_capacity=50), rep("same", max_capacity=5)])
    assert s.best_rep(lead()).rep_id == "same"


def test_full_reps_and_missing_fields_get_no_suggestion():
    full = rep("full")
    full.current = full.max_capacity
    assert Suggester([full]).best_rep(lead()) is None
    assert Suggester([rep()]).best_rep(lead(language=None)) is None


def test_critical_leads_never_get_a_junior():
    s = Suggester([rep("jr", seniority="Junior")])
    assert s.best_rep(critical()) is None


def test_assign_uses_up_capacity_and_clears_the_lead():
    r = rep(max_capacity=1)
    s = Suggester([r])
    stuck = lead()
    s.assign(stuck, s.best_rep(stuck))
    assert stuck.assigned_to == "R-1" and r.remaining == 0
    assert s.best_rep(lead("L-2")) is None


def test_skipped_rep_is_not_suggested_again_for_that_lead():
    s = Suggester([rep("a"), rep("b", expertise="Retail")])
    stuck = lead()
    s.skip(stuck, s.best_rep(stuck))
    assert s.best_rep(stuck).rep_id == "b"
    assert s.best_rep(lead("L-2")).rep_id == "a"


def test_waits_for_enough_decisions_before_training():
    s = Suggester([rep()])
    s.skip(lead(), s.best_rep(lead()))
    assert not s.trained and s.weights == START_WEIGHTS


def test_learns_that_managers_keep_skipping_managers():
    reps = [rep(f"mgr-{i}", seniority="Manager") for i in range(6)] + \
           [rep(f"sr-{i}", expertise="Retail") for i in range(6)]
    s = Suggester(reps)
    for i in range(6):
        stuck = lead(f"L-{i}")
        s.skip(stuck, reps[i])
        s.assign(stuck, reps[6 + i])
    assert s.trained
    assert s.weights[3] < 0  # the Manager weight went negative
    assert s.best_rep(lead("new")).seniority == "Senior"


def test_accept_top_on_the_scale_data():
    leads, reps, _ = run("scale")
    stuck = [l for l in leads if not l.assigned_to]
    s = Suggester(reps)
    assert s.accept_top(leads, 300) == 300
    assert sum(1 for l in stuck if l.assigned_to) == 300
    assert all(r.current <= r.max_capacity for r in reps)


def test_accuracy_counts_one_by_one_picks_but_not_bulk():
    s = Suggester([rep("a", max_capacity=10), rep("b", expertise="Retail", max_capacity=10)])
    assert s.accuracy is None
    first = lead("L-1")
    s.assign(first, s.best_rep(first))  # model liked it and it got assigned: right
    second = lead("L-2")
    s.skip(second, s.best_rep(second))  # model liked it but it got skipped: wrong
    assert s.hits == [True, False] and s.accuracy == 50
    s.accept_top([lead("L-3"), lead("L-4")], 2)
    assert len(s.hits) == 2


def test_plan_never_suggests_a_rep_more_times_than_they_have_room():
    s = Suggester([rep("small", max_capacity=2), rep("big", expertise="Retail", max_capacity=3)])
    picks = s.plan([lead(f"L-{i}") for i in range(10)])
    assert len(picks) == 5
    assert sorted(r.rep_id for r in picks.values()) == ["big", "big", "big", "small", "small"]


def test_accept_top_uses_the_picks_it_was_given():
    a, b = rep("a", max_capacity=1), rep("b", expertise="Retail", max_capacity=1)
    s = Suggester([a, b])
    leads = [lead("L-1"), lead("L-2")]
    s.accept_top(leads, 1, picks={"L-1": b})
    assert leads[0].assigned_to == "b" and a.current == 0


def test_recent_accuracy_only_looks_at_the_last_picks():
    s = Suggester([rep()])
    s.hits = [False] * 30 + [True] * 20
    assert s.recent_accuracy == 100 and s.accuracy == 40


def test_model_can_learn_a_rule_that_mixes_industry_and_seniority():
    # assign same industry non-managers, skip everything else
    reps = [rep(f"sr-same-{i}") for i in range(4)] + [rep(f"sr-other-{i}", expertise="Retail") for i in range(4)] + \
           [rep(f"mgr-same-{i}", seniority="Manager") for i in range(4)]
    s = Suggester(reps)
    for i, r in enumerate(reps):
        stuck = lead(f"L-{i}")
        good = r.expertise == "Technology" and r.seniority != "Manager"
        (s.assign if good else s.skip)(stuck, r)
    new = lead("new")
    assert s.fit(new, rep("x")) > 0.5
    assert s.fit(new, rep("y", expertise="Retail")) < 0.5
    assert s.fit(new, rep("z", seniority="Manager")) < 0.5

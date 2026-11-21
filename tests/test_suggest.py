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
    assert s.weights[2] < 0  # the Manager weight went negative
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
    assert (s.correct, s.checked) == (1, 2) and s.accuracy == 50
    s.accept_top([lead("L-3"), lead("L-4")], 2)
    assert s.checked == 2

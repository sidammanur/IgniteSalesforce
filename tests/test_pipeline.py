from leadrouter.pipeline import run, summary


def test_sample_run_summary_adds_up():
    leads, reps, seconds = run("sample")
    s = summary(leads, reps)
    assert s["leads"] == 100
    assert s["assigned"] + s["review"] == 100
    assert sum(s["review_reasons"].values()) == s["review"]
    assert seconds < 1


def test_every_run_starts_fresh():
    # this is what the Reset button relies on: running twice can't double up rep load
    first = summary(*run("sample")[:2])
    second = summary(*run("sample")[:2])
    assert first == second


def test_scale_run_summary():
    leads, reps, seconds = run("scale")
    s = summary(leads, reps)
    assert s["leads"] == 50_000
    assert s["critical_assigned_pct"] == 100
    assert 0 < s["capacity_used_pct"] <= 100
    assert seconds < 5

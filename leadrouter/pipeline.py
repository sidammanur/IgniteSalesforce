import time
from collections import Counter
from pathlib import Path

from .cleaner import load_leads, load_reps
from .routing import route_leads
from .scoring import score_leads

DATA = Path(__file__).resolve().parent.parent / "data"
DATASETS = {
    "sample": (DATA / "leads_sample.csv", DATA / "reps_sample.csv"),
    "scale": (DATA / "leads_scale.csv", DATA / "reps_scale.csv"),
}
TIERS = ["Critical", "High", "Medium", "Low"]


def run(dataset):
    # reps get reloaded every run so everyone starts back at 0 leads
    leads_path, reps_path = DATASETS[dataset]
    start = time.perf_counter()
    reps = load_reps(reps_path)
    leads = route_leads(score_leads(load_leads(leads_path)), reps)
    return leads, reps, time.perf_counter() - start


def percent(part, whole):
    return 100 * part / whole if whole else 0.0


def summary(leads, reps):
    assigned = [l for l in leads if l.assigned_to]
    critical = [l for l in leads if l.priority == "Critical"]
    return {
        "leads": len(leads),
        "assigned": len(assigned),
        "assigned_pct": percent(len(assigned), len(leads)),
        "review": len(leads) - len(assigned),
        "critical_assigned_pct": percent(sum(1 for l in critical if l.assigned_to), len(critical)),
        "capacity_used_pct": percent(sum(r.current for r in reps), sum(r.max_capacity for r in reps)),
        "reps_full": sum(1 for r in reps if r.max_capacity and r.remaining == 0),
        "review_reasons": Counter(l.review_reason for l in leads if not l.assigned_to),
    }

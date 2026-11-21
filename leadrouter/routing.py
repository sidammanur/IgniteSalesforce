from collections import defaultdict

from .scoring import rank


def build_index(reps):
    # (region, language, industry) -> reps, so matching is a dict lookup instead of a scan
    index = defaultdict(list)
    for rep in reps:
        for region in rep.regions:
            index[(region, rep.language, rep.expertise)].append(rep)
    return index


def matching_reps(lead, index):
    found = {}
    for region in lead.regions:
        for rep in index.get((region, lead.language, lead.vertical), []):
            found[rep.rep_id] = rep  # dict so a rep in both regions isn't counted twice
    return list(found.values())


def pick_rep(reps, levels):
    available = [r for r in reps if r.seniority in levels and r.remaining > 0]
    if not available:
        return None
    # least full (as a %) wins, ties go to whoever got a lead longest ago
    return min(available, key=lambda r: (r.current / r.max_capacity, r.last_assigned, r.rep_id))


def route_leads(leads, reps):
    leads = rank(leads)  # Critical leads have to go first so they get the seniors
    index = build_index(reps)

    for turn, lead in enumerate(leads, start=1):
        lead.assigned_to = None
        lead.review_reason = ""

        if not lead.regions or lead.language is None:
            lead.review_reason = "Missing region or language"
            continue

        candidates = matching_reps(lead, index)
        if not candidates:
            lead.review_reason = "No rep matches region, language and industry"
            continue

        if lead.priority == "Critical":
            if not any(r.seniority in ("Senior", "Manager") for r in candidates):
                lead.review_reason = "Only Junior reps match (Critical needs a Senior or Manager)"
                continue
            rep = pick_rep(candidates, {"Senior"}) or pick_rep(candidates, {"Manager"})
        else:
            # managers are kept as backup for Critical leads
            if not any(r.seniority in ("Junior", "Senior") for r in candidates):
                lead.review_reason = "Only Managers match (kept free for Critical leads)"
                continue
            rep = pick_rep(candidates, {"Junior", "Senior"})

        if rep is None:
            lead.review_reason = "All matching reps are full"
            continue

        rep.current += 1
        rep.last_assigned = turn
        lead.assigned_to = rep.rep_id

    return leads


def manager_review(leads):
    return [lead for lead in leads if lead.assigned_to is None]

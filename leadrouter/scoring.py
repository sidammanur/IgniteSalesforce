ACTIVITY_POINTS = {"Requested Live Demo": 35, "Contact Sales": 35, "Attended Webinar": 25,
                   "Downloaded Whitepaper": 15, "Visited Pricing Page": 5}
# cheat sheet has tech at 15 and healthcare/finance at 10, we bumped each by 5
INDUSTRY_POINTS = {"Technology": 20, "Healthcare": 15, "Finance": 15}


def score_lead(lead):
    if lead.vip:
        return 100

    if lead.size is None:
        score = 20
    elif lead.size >= 1000:
        score = 50
    elif lead.size >= 100:
        score = 30
    else:
        score = 0

    score += ACTIVITY_POINTS.get(lead.activity, 0)
    score += INDUSTRY_POINTS.get(lead.vertical, 0)
    return min(score, 100)  # best case is 105 now, cap it so nothing beats a VIP


def priority(score):
    # cheat sheet says 85/60/40. we use 90 so Critical doesn't swamp the seniors
    if score >= 90:
        return "Critical"
    if score >= 70:
        return "High"
    if score >= 40:
        return "Medium"
    return "Low"


def rank(leads):
    # highest score first, VIPs win ties
    return sorted(leads, key=lambda lead: (lead.score, lead.vip), reverse=True)


def score_leads(leads):
    for lead in leads:
        lead.score = score_lead(lead)
        lead.priority = priority(lead.score)
    return rank(leads)

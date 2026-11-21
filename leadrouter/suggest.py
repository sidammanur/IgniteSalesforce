import math
from collections import Counter, defaultdict

from sklearn.linear_model import LogisticRegression

# Senior is the baseline, so there's no "Senior rep" signal
FEATURES = ["Same industry", "Rep's free room", "Junior rep", "Manager rep",
            "Lead score", "Manager on a high score lead", "Junior on a high score lead"]
# our guess until managers have made enough calls: industry matters most, managers are a last resort
START_WEIGHTS = [2.0, 1.0, -0.5, -1.5, 0.0, 1.0, -0.5]
MIN_DECISIONS = 6
RECENT = 20


def features(lead, rep):
    junior = rep.seniority == "Junior"
    manager = rep.seniority == "Manager"
    score = lead.score / 100
    return [
        float(rep.expertise == lead.vertical),
        rep.remaining / rep.max_capacity,
        float(junior),
        float(manager),
        score,
        manager * score,
        junior * score,
    ]


class Suggester:
    # suggests the closest rep for leads stuck in Manager Review and learns from what managers pick

    def __init__(self, reps):
        self.by_area = defaultdict(list)
        for rep in reps:
            for region in rep.regions:
                self.by_area[(region, rep.language)].append(rep)
        self.weights = list(START_WEIGHTS)
        self.bias = 0.0
        self.decisions = []  # (features, 1 for assigned / 0 for skipped)
        self.skipped = set()
        self.trained = False
        self.hits = []  # before each manager click, did the model guess the same thing?

    def fit(self, lead, rep):
        z = self.bias + sum(w * x for w, x in zip(self.weights, features(lead, rep)))
        return 1 / (1 + math.exp(-z))

    def best_rep(self, lead, held=None):
        # region and language still have to match, industry is the part we let slide
        if not lead.regions or lead.language is None:
            return None
        held = held or {}
        options = {}
        for region in lead.regions:
            for rep in self.by_area.get((region, lead.language), []):
                if rep.remaining - held.get(rep.rep_id, 0) <= 0 or (lead.lead_id, rep.rep_id) in self.skipped:
                    continue
                if lead.priority == "Critical" and rep.seniority == "Junior":
                    continue
                options[rep.rep_id] = rep
        if not options:
            return None
        return min(options.values(), key=lambda r: (-self.fit(lead, r), r.rep_id))

    def plan(self, leads):
        # go down the queue best lead first and hold a slot for every suggestion,
        # so a rep with 6 free slots gets suggested 6 times instead of 300
        held = Counter()
        picks = {}
        for lead in leads:
            if lead.assigned_to:
                continue
            rep = self.best_rep(lead, held)
            if rep:
                held[rep.rep_id] += 1
                picks[lead.lead_id] = rep
        return picks

    def record_guess(self, lead, rep, assigned):
        self.hits.append((self.fit(lead, rep) >= 0.5) == assigned)

    @property
    def accuracy(self):
        return 100 * sum(self.hits) / len(self.hits) if self.hits else None

    @property
    def recent_accuracy(self):
        recent = self.hits[-RECENT:]
        return 100 * sum(recent) / len(recent) if recent else None

    def assign(self, lead, rep, bulk=False):
        # bulk accepts still train the model but don't count toward accuracy, nobody looked at them one by one
        if not bulk:
            self.record_guess(lead, rep, True)
        self.decisions.append((features(lead, rep), 1))
        rep.current += 1
        lead.assigned_to = rep.rep_id
        lead.review_reason = "Assigned from Manager Review"
        if not bulk:
            self.retrain()

    def skip(self, lead, rep):
        self.record_guess(lead, rep, False)
        self.decisions.append((features(lead, rep), 0))
        self.skipped.add((lead.lead_id, rep.rep_id))
        self.retrain()

    def accept_top(self, leads, n, picks=None):
        # pass in the picks that are on screen so bulk accept gives the same reps the manager saw
        picks = self.plan(leads) if picks is None else picks
        done = 0
        for lead in leads:
            if done == n:
                break
            if lead.lead_id in picks:
                self.assign(lead, picks[lead.lead_id], bulk=True)
                done += 1
        self.retrain()
        return done

    def retrain(self):
        labels = [y for _, y in self.decisions]
        if len(labels) < MIN_DECISIONS or len(set(labels)) < 2:
            return
        # C=10 means light regularisation, there are only a handful of decisions early on
        model = LogisticRegression(C=10, class_weight="balanced", max_iter=1000)
        model.fit([x for x, _ in self.decisions], labels)
        self.weights = list(model.coef_[0])
        self.bias = float(model.intercept_[0])
        self.trained = True

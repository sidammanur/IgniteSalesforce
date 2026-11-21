import math
from collections import defaultdict

from sklearn.linear_model import LogisticRegression

FEATURES = ["Same industry", "Rep's free room", "Manager", "Manager on a high score lead"]
# our guess until managers have made enough calls: industry matters most, managers are a last resort
START_WEIGHTS = [2.0, 1.0, -1.5, 1.0]
MIN_DECISIONS = 10


def features(lead, rep):
    manager = rep.seniority == "Manager"
    return [
        float(rep.expertise == lead.vertical),
        rep.remaining / rep.max_capacity,
        float(manager),
        manager * lead.score / 100,
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
        # accuracy: before each manager click, did the model guess the same thing?
        self.checked = 0
        self.correct = 0

    def fit(self, lead, rep):
        z = self.bias + sum(w * x for w, x in zip(self.weights, features(lead, rep)))
        return 1 / (1 + math.exp(-z))

    def best_rep(self, lead):
        # region and language still have to match, industry is the part we let slide
        if not lead.regions or lead.language is None:
            return None
        options = {}
        for region in lead.regions:
            for rep in self.by_area.get((region, lead.language), []):
                if rep.remaining == 0 or (lead.lead_id, rep.rep_id) in self.skipped:
                    continue
                if lead.priority == "Critical" and rep.seniority == "Junior":
                    continue
                options[rep.rep_id] = rep
        if not options:
            return None
        return min(options.values(), key=lambda r: (-self.fit(lead, r), r.rep_id))

    def score_guess(self, lead, rep, label):
        self.checked += 1
        self.correct += (self.fit(lead, rep) >= 0.5) == label

    @property
    def accuracy(self):
        return 100 * self.correct / self.checked if self.checked else None

    def assign(self, lead, rep, bulk=False):
        # bulk accepts still train the model but don't count toward accuracy, nobody looked at them one by one
        if not bulk:
            self.score_guess(lead, rep, True)
        self.decisions.append((features(lead, rep), 1))
        rep.current += 1
        lead.assigned_to = rep.rep_id
        lead.review_reason = "Assigned from Manager Review"
        if not bulk:
            self.retrain()

    def skip(self, lead, rep):
        self.score_guess(lead, rep, False)
        self.decisions.append((features(lead, rep), 0))
        self.skipped.add((lead.lead_id, rep.rep_id))
        self.retrain()

    def accept_top(self, leads, n):
        done = 0
        for lead in leads:
            if done == n:
                break
            rep = None if lead.assigned_to else self.best_rep(lead)
            if rep:
                self.assign(lead, rep, bulk=True)
                done += 1
        self.retrain()
        return done

    def retrain(self):
        labels = [y for _, y in self.decisions]
        if len(labels) < MIN_DECISIONS or len(set(labels)) < 2:
            return
        model = LogisticRegression(class_weight="balanced").fit([x for x, _ in self.decisions], labels)
        self.weights = list(model.coef_[0])
        self.bias = float(model.intercept_[0])
        self.trained = True

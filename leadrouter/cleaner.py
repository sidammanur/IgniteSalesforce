import csv
import re
from collections import Counter
from dataclasses import dataclass
from typing import Optional

MISSING = {"", "n/a", "none", "null", "nan", "unknown", "-"}

LANGUAGES = {"english": "English", "en": "English",
             "spanish": "Spanish", "es": "Spanish",
             "german": "German", "de": "German"}
VERTICALS = {"technology": "Technology", "finance": "Finance", "healthcare": "Healthcare",
             "manufacturing": "Manufacturing", "retail": "Retail"}
SENIORITY = {"junior": "Junior", "jr": "Junior",
             "senior": "Senior", "sr": "Senior",
             "manager": "Manager", "mgr": "Manager"}
ACTIVITIES = {"requestedlivedemo": "Requested Live Demo",
              "contactsales": "Contact Sales",
              "attendedwebinar": "Attended Webinar",
              "downloadedwhitepaper": "Downloaded Whitepaper",
              "visitedpricingpage": "Visited Pricing Page"}


def clean(value):
    return " ".join(str(value).split()).lower()


def squash(value):
    return re.sub(r"[^a-z0-9]", "", clean(value))


def lookup(value, table):
    if clean(value) in MISSING:
        return None
    return table.get(squash(value))


def parse_regions(value):
    if clean(value) in MISSING:
        return frozenset()
    key = squash(value)
    found = set()
    if key == "na" or "nort" in key:
        found.add("North America")
    if "eur" in key:
        found.add("Europe")
    if "asia" in key or "apac" in key or "pacific" in key:
        found.add("Asia-Pacific")
    return frozenset(found)


def parse_activity(value):
    # labeling things as long as they dont already have one
    text = clean(value)
    if text in MISSING:
        return None
    return ACTIVITIES.get(squash(text), text.title())


def to_number(text):
    if text.endswith("k"):
        return float(text[:-1]) * 1000
    return float(text)


def parse_size(value):
    # make sure things like 1,000 and 1000-2000 are fixed
    text = clean(value).replace(",", "").replace(" ", "")
    if text in MISSING:
        return None
    try:
        nums = [to_number(part) for part in text.split("-")]
        size = round(sum(nums) / len(nums))
    except (ValueError, OverflowError):
        return None
    return size if size > 0 else None


def parse_int(value):
    try:
        return int(float(clean(value).replace(",", "")))
    except (ValueError, OverflowError):
        return None


@dataclass
class Lead:
    lead_id: str
    company: str
    regions: frozenset
    language: Optional[str]
    vertical: Optional[str]
    size: Optional[int]
    activity: Optional[str]
    vip: bool


@dataclass
class Rep:
    rep_id: str
    name: str
    regions: frozenset
    language: Optional[str]
    expertise: Optional[str]  # None = no listed specialty
    seniority: str
    current: int
    max_capacity: int

    @property
    def remaining(self):
        return max(0, self.max_capacity - self.current)


def unique_id(raw, row_num, prefix, seen):
    """Duplicate IDs belong to different companies, so keep both: L-1, L-1#2, ...
    A missing ID is replaced with one based on the row number."""
    # docstring ahahaha engr 102 coming in clutch T_T
    rid = (raw or "").strip() or f"{prefix}-ROW-{row_num}"
    seen[rid] += 1
    if seen[rid] == 1:
        return rid
    return f"{rid}#{seen[rid]}"


def clean_leads(rows):
    leads = []
    seen = Counter()
    for row_num, row in enumerate(rows, start=1):
        company = " ".join((row.get("Company_Name") or "").split())
        leads.append(Lead(
            lead_id=unique_id(row.get("Lead_ID"), row_num, "LEAD", seen),
            company=company or "(unknown)",
            regions=parse_regions(row.get("Region")),
            language=lookup(row.get("Language"), LANGUAGES),
            vertical=lookup(row.get("Industry_Vertical"), VERTICALS),
            size=parse_size(row.get("Company_Size")),
            activity=parse_activity(row.get("Recent_Activity")),
            # only an explicit True counts, so 'Unknown' can't make a lead Critical
            vip=clean(row.get("VIP_Referral")) in {"true", "yes", "1"},
        ))
    return leads


def clean_reps(rows):
    reps = []
    seen = Counter()
    for row_num, row in enumerate(rows, start=1):
        rep_id = unique_id(row.get("Rep_ID"), row_num, "REP", seen)
        # the files repeat the ID in the name: 'Avery Davis (R-2)'
        name = " ".join((row.get("Name") or "").split())
        name = re.sub(r"\s*\(.*?\)$", "", name)
        reps.append(Rep(
            rep_id=rep_id,
            name=name or rep_id,
            regions=parse_regions(row.get("Region")),
            language=lookup(row.get("Language"), LANGUAGES),
            expertise=lookup(row.get("Industry_Vertical_Expertise"), VERTICALS),
            # unknown rank -> Junior, the safest choice since Juniors never get Critical leads
            seniority=lookup(row.get("Seniority_Level"), SENIORITY) or "Junior",
            current=max(parse_int(row.get("Current_Capacity")) or 0, 0),
            # a negative or unreadable limit can't be trusted, so that rep gets no leads
            max_capacity=max(parse_int(row.get("Max_Capacity")) or 0, 0),
        ))
    return reps


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_leads(path):
    return clean_leads(read_csv(path))


def load_reps(path):
    return clean_reps(read_csv(path))

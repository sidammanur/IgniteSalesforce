import time
from pathlib import Path

import pytest

from leadrouter.cleaner import clean_leads, clean_reps, load_leads, load_reps, parse_regions, parse_size

DATA = Path(__file__).resolve().parent.parent / "data"
NA, EU, AP = "North America", "Europe", "Asia-Pacific"


def lead(**fields):
    row = {"Lead_ID": "L-1", "Company_Name": "Acme", "Region": "Europe", "Language": "English",
           "Industry_Vertical": "Technology", "Company_Size": "500",
           "Recent_Activity": "Attended Webinar", "VIP_Referral": "False"}
    return clean_leads([{**row, **fields}])[0]


def rep(**fields):
    row = {"Rep_ID": "R-1", "Name": "Pat Jones (R-1)", "Region": "Europe", "Language": "English",
           "Industry_Vertical_Expertise": "Technology", "Seniority_Level": "Senior",
           "Current_Capacity": "0", "Max_Capacity": "20"}
    return clean_reps([{**row, **fields}])[0]


@pytest.mark.parametrize("raw, expected", [
    ("NA", {NA}), ("North  Amer", {NA}), ("Nort America", {NA}), (" North America ", {NA}),
    ("EUR", {EU}), ("Europ", {EU}), (" EUROPE ", {EU}),
    ("APAC", {AP}), ("Asa-Pacific", {AP}), ("Asia.  Pacific", {AP}),
    ("NORTH   AMERICA Asia-Pacific ", {NA, AP}), ("ASIA   PACIFICEurope", {AP, EU}),
    ("", set()), ("N/A", set()), (None, set()), ("Mars", set()),
])
def test_regions(raw, expected):
    assert parse_regions(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("1015", 1015), ("1,000", 1000), ("5k", 5000), ("500-1000", 750),
    ("", None), ("null", None), ("None", None), ("N/A", None),
    ("0", None), ("-5", None), ("lots", None), ("inf", None),
])
def test_company_size(raw, expected):
    assert parse_size(raw) == expected


@pytest.mark.parametrize("raw, expected", [("EN", "English"), ("spanish", "Spanish"), ("DE", "German"),
                                           ("Klingon", None), ("", None)])
def test_language(raw, expected):
    assert lead(Language=raw).language == expected


def test_vertical_whitespace_and_unknown():
    assert lead(Industry_Vertical=" Finance").vertical == "Finance"
    assert lead(Industry_Vertical="Technology ").vertical == "Technology"
    assert lead(Industry_Vertical="Unknown").vertical is None


def test_activity():
    assert lead(Recent_Activity="requested live demo ").activity == "Requested Live Demo"
    assert lead(Recent_Activity="Downloaded  Whitepaper").activity == "Downloaded Whitepaper"
    assert lead(Recent_Activity="Started Free Trial").activity == "Started Free Trial"
    assert lead(Recent_Activity="N/A").activity is None


@pytest.mark.parametrize("raw, expected", [("True", True), ("False", False), ("Unknown", False), ("", False)])
def test_vip_only_counts_an_explicit_true(raw, expected):
    assert lead(VIP_Referral=raw).vip is expected


def test_lead_with_every_field_missing_is_kept():
    blank = lead(Company_Name="", Region="", Language="", Industry_Vertical="",
                 Company_Size="", Recent_Activity="", VIP_Referral="")
    assert blank.company == "(unknown)"
    assert (blank.regions, blank.language, blank.vertical, blank.size, blank.activity, blank.vip) == \
        (frozenset(), None, None, None, None, False)


def test_short_row_does_not_crash():
    leads = clean_leads([{"Lead_ID": "L-1", "Region": None}])
    assert leads[0].regions == frozenset() and leads[0].size is None


def test_duplicate_and_missing_ids_are_made_unique():
    leads = clean_leads([{"Lead_ID": "L-1"}, {"Lead_ID": "L-1"}, {"Lead_ID": ""}])
    assert [l.lead_id for l in leads] == ["L-1", "L-1#2", "LEAD-ROW-3"]


@pytest.mark.parametrize("raw, expected", [("sr", "Senior"), (" junior", "Junior"), ("MGR", "Manager"),
                                           ("Director", "Junior"), ("", "Junior")])
def test_seniority_unknown_defaults_to_junior(raw, expected):
    assert rep(Seniority_Level=raw).seniority == expected


@pytest.mark.parametrize("raw, expected", [("20", 20), ("-20", 0), ("abc", 0), ("", 0)])
def test_bad_max_capacity_means_no_leads(raw, expected):
    assert rep(Max_Capacity=raw).max_capacity == expected


def test_rep_name_and_remaining():
    r = rep(Current_Capacity="30")
    assert r.name == "Pat Jones"
    assert r.remaining == 0  # never negative
    assert rep(Name="").name == "R-1"
    assert rep(Industry_Vertical_Expertise="Unknown").expertise is None


def test_sample_data():
    leads = {l.lead_id: l for l in load_leads(DATA / "leads_sample.csv")}
    reps = {r.rep_id: r for r in load_reps(DATA / "reps_sample.csv")}
    assert len(leads) == 100 and len(reps) == 10
    assert "L-1057#2" in leads  # L-1057 appears twice
    assert leads["L-1004"].regions == {NA, AP} and leads["L-1004"].vip
    assert leads["L-1003"].size == 5000
    assert reps["R-9"].max_capacity == 0  # file says -20


def test_scale_data_is_fast_and_complete():
    start = time.perf_counter()
    leads = load_leads(DATA / "leads_scale.csv")
    reps = load_reps(DATA / "reps_scale.csv")
    assert time.perf_counter() - start < 2

    assert len(leads) == len({l.lead_id for l in leads}) == 50_000
    assert len(reps) == 1_600
    assert all(l.regions and l.language for l in leads)
    assert all(r.regions and r.language and r.remaining >= 0 for r in reps)
    assert {r.seniority for r in reps} == {"Junior", "Senior", "Manager"}

# run with: streamlit run dashboard.py
import pandas as pd
import streamlit as st

from leadrouter.pipeline import TIERS, run, summary
from leadrouter.suggest import FEATURES, MIN_DECISIONS, RECENT, START_WEIGHTS, Suggester

LEVELS = ["Junior", "Senior", "Manager"]
REP_STATUSES = ["Full", "Has room", "No capacity"]

st.set_page_config(page_title="Ignite Lead Router", layout="wide")
st.title("Ignite Lead Router")
st.write("Scores each lead and sends it to a rep with the same region, language and industry. "
         "Leads nobody can take go to Manager Review.")


def leads_table(leads, reps):
    names = {r.rep_id: r.name for r in reps}
    df = pd.DataFrame([{
        "Lead ID": l.lead_id,
        "Company": l.company,
        "Priority": l.priority,
        "Score": l.score,
        "VIP": l.vip,
        "Region": ", ".join(sorted(l.regions)) or "Unknown",
        "Language": l.language or "Unknown",
        "Industry": l.vertical or "Unknown",
        "Size": l.size,
        "Activity": l.activity or "None",
        "Status": "Assigned" if l.assigned_to else "Manager Review",
        "Assigned To": f"{names[l.assigned_to]} ({l.assigned_to})" if l.assigned_to else "",
        "Review Reason": l.review_reason,
    } for l in leads])
    df["Size"] = df["Size"].astype("Int64")  # otherwise pandas shows 1015.0
    return df


def rep_status(rep):
    if rep.max_capacity == 0:
        return "No capacity"
    return "Full" if rep.remaining == 0 else "Has room"


def reps_table(reps):
    df = pd.DataFrame([{
        "Rep": f"{r.name} ({r.rep_id})",
        "Seniority": r.seniority,
        "Region": ", ".join(sorted(r.regions)) or "Unknown",
        "Language": r.language or "Unknown",
        "Expertise": r.expertise or "Generalist",
        "Leads": r.current,
        "Max": r.max_capacity,
        "Load %": round(100 * r.current / r.max_capacity) if r.max_capacity else 0,
        "Status": rep_status(r),
    } for r in reps])
    return df.sort_values(["Load %", "Leads"], ascending=False)


def why(lead, rep):
    industry = "same industry" if rep.expertise == lead.vertical else f"{rep.expertise or 'generalist'} rep"
    return f"{rep.seniority}, {industry}, {rep.remaining} of {rep.max_capacity} free"


def review_table(leads, suggester, picks):
    rows = []
    for l in leads:
        if l.assigned_to:
            continue
        rep = picks.get(l.lead_id)
        rows.append({
            "Lead ID": l.lead_id,
            "Company": l.company,
            "Priority": l.priority,
            "Score": l.score,
            "Suggested Rep": f"{rep.name} ({rep.rep_id})" if rep else "",
            "Fit": round(100 * suggester.fit(l, rep)) if rep else None,
            "Why": why(l, rep) if rep else "No rep left with room in this region and language",
            "Industry": l.vertical or "Unknown",
            "Region": ", ".join(sorted(l.regions)) or "Unknown",
            "Language": l.language or "Unknown",
            "Review Reason": l.review_reason,
        })
    return pd.DataFrame(rows, columns=["Lead ID", "Company", "Priority", "Score", "Suggested Rep", "Fit", "Why",
                                       "Industry", "Region", "Language", "Review Reason"])


def refresh():
    # rebuild the tables after a run or after a manager assigns/skips something
    r = st.session_state.run
    picks = r["suggester"].plan(r["leads"])
    st.session_state.results = {
        "summary": summary(r["leads"], r["reps"]),
        "leads": leads_table(r["leads"], r["reps"]),
        "reps": reps_table(r["reps"]),
        "review": review_table(r["leads"], r["suggester"], picks),
        "picks": picks,
    }


def decide(lead_ids, action):
    # use the rep that was on screen, not a fresh pick, so nobody gets assigned to a rep they never saw
    r = st.session_state.run
    picks = st.session_state.results["picks"]
    for lead_id in lead_ids:
        if lead_id in picks:
            action(r["by_id"][lead_id], picks[lead_id])
    refresh()
    st.rerun()


if "run" not in st.session_state:
    st.session_state.run = None

col1, col2, col3 = st.columns(3)
run_sample = col1.button("Run Sample (100 leads)", width="stretch")
run_scale = col2.button("Run Scale (50,000 leads)", type="primary", width="stretch")
if col3.button("Reset", width="stretch"):
    st.session_state.run = None

if run_sample or run_scale:
    dataset = "sample" if run_sample else "scale"
    with st.spinner(f"Running the {dataset} dataset..."):
        leads, reps, seconds = run(dataset)
        st.session_state.run = {
            "dataset": dataset,
            "seconds": seconds,
            "leads": leads,
            "reps": reps,
            "by_id": {l.lead_id: l for l in leads},
            "suggester": Suggester(reps),
        }
        refresh()

if st.session_state.run is None:
    st.info("Click Run Sample or Run Scale to begin.")
    st.stop()

current = st.session_state.run
results = st.session_state.results
s = results["summary"]
leads_df = results["leads"]
reps_df = results["reps"]
seconds = current["seconds"]
took = f"{seconds:.2f}s" if seconds >= 0.1 else f"{seconds * 1000:.0f} ms"

st.subheader(f"{current['dataset'].title()} run")
st.markdown(f"**{s['leads']:,} leads in {took}.** {s['assigned']:,} assigned ({s['assigned_pct']:.1f}%), "
            f"{s['review']:,} sent to Manager Review.")
k1, k2, k3, _ = st.columns([1, 1, 1, 2])
k1.metric("Critical leads assigned", f"{s['critical_assigned_pct']:.0f}%")
k2.metric("Rep capacity used", f"{s['capacity_used_pct']:.0f}%")
k3.metric("Reps maxed out", f"{s['reps_full']:,}")

chart_col, reason_col = st.columns([3, 2])
with chart_col:
    st.markdown("**Leads by priority**")
    by_tier = pd.crosstab(leads_df["Priority"], leads_df["Status"]).reindex(
        index=TIERS, columns=["Assigned", "Manager Review"], fill_value=0)
    st.bar_chart(by_tier, color=["#1F5F8B", "#C8742B"], height=260, sort=False)
with reason_col:
    st.markdown("**Why leads went to Manager Review**")
    if s["review_reasons"]:
        reasons = pd.DataFrame(s["review_reasons"].most_common(), columns=["Reason", "Leads"])
        st.dataframe(reasons, hide_index=True, width="stretch")
    else:
        st.success("Every lead was assigned.")

# a radio instead of st.tabs because tabs jump back to the first one whenever a table row gets picked
page = st.radio("View", ["Lead Queue", "Manager Review", "Rep Capacity"], horizontal=True,
                label_visibility="collapsed", key="view")
score_column = {"Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d")}

if page == "Lead Queue":
    f1, f2, f3, f4 = st.columns([2, 2, 1, 2])
    tiers = f1.multiselect("Priority", TIERS, default=TIERS)
    regions = f2.multiselect("Region", ["North America", "Europe", "Asia-Pacific"])
    status = f3.selectbox("Status", ["All", "Assigned", "Manager Review"])
    search = f4.text_input("Search company, lead or rep")

    view = leads_df[leads_df["Priority"].isin(tiers)]
    if regions:
        view = view[view["Region"].apply(lambda r: any(region in r for region in regions))]
    if status != "All":
        view = view[view["Status"] == status]
    if search:
        text = view["Company"] + " " + view["Lead ID"] + " " + view["Assigned To"]
        view = view[text.str.contains(search, case=False, regex=False)]

    st.caption(f"Showing {len(view):,} of {len(leads_df):,} leads, highest score first")
    st.dataframe(view.drop(columns=["Status", "Review Reason"]), hide_index=True, width="stretch",
                 height=500, column_config=score_column)

if page == "Manager Review":
    suggester = current["suggester"]
    review = results["review"]
    has_rep = review["Suggested Rep"] != ""
    st.caption(f"{len(review):,} leads still need a rep and {has_rep.sum():,} of them can get one. Each rep is "
               "only suggested as many times as they have free slots. Region and language always match, the "
               "industry might not, so a manager makes the call.")
    picked = st.multiselect("Priority", TIERS, default=TIERS, key="review_tiers")
    review = review[review["Priority"].isin(picked)]
    can_place = int((review["Suggested Rep"] != "").sum())
    table = st.dataframe(
        review, hide_index=True, width="stretch", height=450, on_select="rerun", selection_mode="multi-row",
        key=f"review_rows_{len(suggester.decisions)}",  # new key so old picks don't stick around after a decision
        column_config={
            **score_column,
            "Suggested Rep": st.column_config.TextColumn(width="medium"),
            "Why": st.column_config.TextColumn(width="large"),
            "Fit": st.column_config.ProgressColumn("Fit", min_value=0, max_value=100, format="%d%%"),
        })
    chosen = review.iloc[table.selection.rows]["Lead ID"].tolist()

    # bulk buttons only touch the leads shown with the current priority filter
    shown = [current["by_id"][lead_id] for lead_id in review["Lead ID"]]
    a1, a2, a3, a4, a5 = st.columns([1, 1, 1, 1.5, 1.5], vertical_alignment="bottom")
    if a1.button(f"Assign selected ({len(chosen)})", disabled=not chosen, width="stretch"):
        decide(chosen, suggester.assign)
    if a2.button(f"Skip selected ({len(chosen)})", disabled=not chosen, width="stretch"):
        decide(chosen, suggester.skip)
    most = max(can_place, 1)
    top_n = a3.number_input("How many", min_value=1, max_value=most, value=min(100, most))
    bulk = None
    if a4.button(f"Accept the top {top_n:,}", disabled=not can_place, width="stretch"):
        bulk = top_n
    accept_all = f"Accept all {can_place:,} with a rep" if can_place else "No reps left with room"
    if a5.button(accept_all, disabled=not can_place, width="stretch"):
        bulk = can_place
    left = len(review) - can_place
    if left:
        a5.caption(f"{left:,} have no rep with room left, they stay here.")
    if bulk:
        done = suggester.accept_top(shown, bulk, results["picks"])
        st.session_state.note = f"Assigned {done:,} leads."
        refresh()
        st.rerun()
    if "note" in st.session_state:
        st.success(st.session_state.pop("note"))

    st.download_button("Download as CSV", review.to_csv(index=False), "manager_review.csv", "text/csv")

    st.markdown("**What the ranker has learned**")
    assigned = sum(label for _, label in suggester.decisions)
    skipped = len(suggester.decisions) - assigned
    if suggester.trained:
        st.caption(f"Logistic regression trained on {len(suggester.decisions)} decisions "
                   f"({assigned:,} assigned, {skipped:,} skipped). It retrains after every decision.")
    else:
        st.caption(f"Using our starting weights until there are {MIN_DECISIONS} decisions with at least one "
                   f"assign and one skip ({assigned:,} assigned, {skipped:,} skipped so far).")
    weights_col, accuracy_col = st.columns([3, 2])
    weights = pd.DataFrame({"Signal": FEATURES, "Start": START_WEIGHTS, "Now": suggester.weights})
    weights_col.dataframe(weights, hide_index=True, width="stretch",
                          column_config={"Start": st.column_config.NumberColumn(format="%.2f"),
                                         "Now": st.column_config.NumberColumn(format="%.2f")})
    recent = suggester.recent_accuracy
    hits = suggester.hits
    accuracy_col.metric(f"Model accuracy, last {min(len(hits), RECENT) or RECENT} picks",
                        "No picks yet" if recent is None else f"{recent:.0f}%")
    if hits:
        accuracy_col.caption(f"Before every Assign or Skip the model guesses what you'll pick. It has been right "
                             f"{sum(hits)} of {len(hits)} times overall ({suggester.accuracy:.0f}%). "
                             "Bulk accepts are not used when checking the model's accuracy.")
    else:
        accuracy_col.caption("Before every Assign or Skip the model guesses what you'll pick. "
                             "Bulk accepts are not used when checking the model's accuracy.")

if page == "Rep Capacity":
    st.markdown("**Load by seniority**")
    by_level = reps_df.groupby("Seniority")[["Leads", "Max"]].sum().reindex(LEVELS).dropna()
    by_level["Free"] = by_level["Max"] - by_level["Leads"]
    st.bar_chart(by_level[["Leads", "Free"]], horizontal=True, color=["#1F5F8B", "#D9D5CC"],
                 height=200, sort=False)

    c1, c2 = st.columns([2, 3])
    levels = c1.multiselect("Seniority", LEVELS, default=LEVELS)
    statuses = c2.multiselect("Status", REP_STATUSES, default=REP_STATUSES, key="rep_status")
    reps_view = reps_df[reps_df["Seniority"].isin(levels) & reps_df["Status"].isin(statuses)]
    st.caption(f"Showing {len(reps_view):,} of {len(reps_df):,} reps, busiest first")
    st.dataframe(reps_view, hide_index=True, width="stretch", height=500, column_config={
        "Load %": st.column_config.ProgressColumn("Load", min_value=0, max_value=100, format="%d%%"),
    })

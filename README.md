# Lead Router

Prioritises sales leads and routes them to the right rep (Salesforce Ignite Challenge).

Cleaning, scoring, routing and the dashboard all work. Keep adding to this as we finish stuff.

## Setup

```
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Put the four CSVs (`leads_sample.csv`, `reps_sample.csv`, `leads_scale.csv`, `reps_scale.csv`) in `data/`.

## Run the dashboard

```
streamlit run dashboard.py
```

Hit Run Scale for the real demo. The sample only has 10 reps, so most of its leads end up in Manager Review.

## Use it from Python

```python
from leadrouter.pipeline import run, summary

leads, reps, seconds = run("scale")
print(summary(leads, reps))
```

## Run the tests

```
python -m pytest
```

## Cleaning rules (summary)

Quick rundown of how we clean up the lead data:

- **Save everything:** We don't throw anything away. If a field is bad or missing, we just swap it for None or a safe default and keep the record moving.

- **Tidy up text:** Things like region, language, and seniority get lowercased, stripped of weird punctuation, and matched against our alias table. If a record lists two regions (like "North America Asia-Pacific"), we keep both.

- **Company size:** We handle all sorts of formats, like 1,000, 5k, or ranges like 500-1000 (which we average out). Any zero, negative, or garbled numbers just get marked as missing.

- **VIP status:** Only an explicit True counts for VIP_Referral. Anything blank or unknown defaults to False.

- **Handling duplicates:** If two leads share the same Lead_ID, we assume they're different companies and keep both, just renaming the later ones to something like L-123#2. If an ID is totally missing, we assign it LEAD-ROW-<n>.

- **Rep capacity:** If a rep's capacity looks negative or unreadable, we treat it as zero. If we don't know a rep's seniority, we default them to Junior so they never get assigned Critical leads by mistake.

## Scoring

Every lead gets 0 to 100 points:

- **Company size:** 1000+ employees is 50, 100 to 999 is 30, under 100 is 0, and unknown gets 20.
- **Activity:** live demo or contact sales is 35, webinar 25, whitepaper 15, pricing page 5.
- **Industry:** Technology 20, Healthcare and Finance 15.
- **VIP referrals** skip all that and get 100.

Tiers: 90+ Critical, 70+ High, 40+ Medium, everything else Low. The cheat sheet uses 85/60/40 with smaller industry points, but that made about half the leads Critical, way more than the Senior reps can cover. Our numbers land close to the 10/20/40/30 split it asks for.

## Routing

- Leads go out highest score first, so Critical leads get first pick of the reps.
- A rep has to match the lead's region, language and industry. A lead with no industry can go to a generalist.
- Critical leads go to a Senior, or a Manager if every matching Senior is full. Never a Junior.
- Everything else goes to Juniors and Seniors. Managers are pricey, so we keep them free for Critical leads.
- Out of the reps who qualify, the least busy one (as a % of their max) gets it. Ties go to whoever got a lead longest ago.
- If nobody can take it, it goes to Manager Review with the reason why.

On the 50k file: 89.7% assigned, every Critical lead assigned, 95% of rep capacity used, under 1.5 seconds.

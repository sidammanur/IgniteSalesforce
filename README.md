# Lead Router

Prioritises sales leads and routes them to the right rep (Salesforce Ignite Challenge).

Status: data cleaner done. Scoring, routing, API and dashboard are next.

## Setup

```
pip install -r requirements.txt
```

Put the four CSVs (`leads_sample.csv`, `reps_sample.csv`, `leads_scale.csv`, `reps_scale.csv`) in `data/`.

## Use the cleaner

```python
from leadrouter import load_leads, load_reps

leads = load_leads("data/leads_scale.csv")
reps = load_reps("data/reps_scale.csv")
```

## Run the tests

```
python -m pytest
```

## Cleaning rules (summary)

- Nothing is dropped. Bad or missing fields become `None` (or a safe default) and the record is kept.
- Region/language/vertical/seniority/activity: lower-case, strip punctuation, look up in an alias table. Two-region strings ("North America Asia-Pacific") keep both regions.
- Company size: handles `1,000`, `5k`, `500-1000` (midpoint) and blanks; zero, negative or garbage values become missing.
- `VIP_Referral`: only an explicit `True` counts. `Unknown`/blank is False.
- Duplicate Lead_IDs are different companies, so both are kept; later ones become `L-123#2`. Missing IDs become `LEAD-ROW-<n>`.
- Rep capacity: negative or unreadable means the rep takes no leads. Unknown seniority defaults to Junior so it can never receive Critical leads.

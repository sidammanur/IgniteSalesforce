# Lead Router

Prioritises sales leads and routes them to the right rep (Salesforce Ignite Challenge).

Status: data cleaner done. Scoring, routing, API and dashboard are next.

## Setup

```
pip install -r requirements.txt
```

Put the four CSVs (`leads_sample.csv`, `reps_sample.csv`, `leads_scale.csv`, `reps_scale.csv`) in `data/`.

## Run the cleaner

```
python leadrouter/cleaner.py data/leads_scale.csv --reps data/reps_scale.csv
```

Prints how many rows were read/kept, how long it took, and how many records needed each kind of repair.

## Run the tests

```
python -m pytest
```

## Cleaning rules (summary)

- Nothing is dropped. Bad fields become `None` plus a flag; only fully blank rows are skipped (and counted).
- Region/language/vertical/seniority/activity: lower-case, strip punctuation, look up in an alias table, typo-tolerant fallback. Two-region strings ("North America Asia-Pacific") keep both regions.
- Company size: handles `1,000`, `5k`, `500-1000` (midpoint), blanks; zero, negative or impossible (> 10 million) values become missing.
- `VIP_Referral`: only an explicit yes is True. `Unknown`/blank is False and flagged.
- Duplicate Lead_IDs are different companies, so both are kept; later ones become `L-123#2`.
- Rep capacity: negative/invalid means the rep takes no leads (`--negative-capacity abs` treats a negative as a sign typo instead). Unknown seniority defaults to Junior so it can never receive Critical leads.

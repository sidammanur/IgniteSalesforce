# Lead Router

Prioritises sales leads and routes them to the right rep (Salesforce Ignite Challenge).
(Just add in stuff to the read me as u end up completing the things we need)
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

Hey! Here’s a quick rundown of how we clean up the lead data:

-Save everything: We don't throw anything away. If a field is bad or missing, we just swap it for None or a safe default and keep the record moving.

-Tidy up text: Things like region, language, and seniority get lowercased, stripped of weird punctuation, and matched against our alias table. If a record lists two regions (like "North America Asia-Pacific"), we keep both.

-Company size: We handle all sorts of formats—like 1,000, 5k, or ranges like 500-1000 (which we average out). Any zero, negative, or garbled numbers just get marked as missing.

-VIP status: Only an explicit True counts for VIP_Referral. Anything blank or unknown defaults to False.

-Handling duplicates: If two leads share the same Lead_ID, we assume they're different companies and keep both, just renaming the later ones to something like L-123#2. If an ID is totally missing, we assign it LEAD-ROW-<n>.

-Rep capacity: If a rep's capacity looks negative or unreadable, we treat it as zero. If we don't know a rep's seniority, we default them to Junior so they never get assigned Critical leads by mistake.

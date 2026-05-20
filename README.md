# List Enrichment Dropbox

Simple Streamlit app: upload a CSV → validate → send rows to a Clay webhook.

## Quick start

```bash
cd list-enrichment-dropbox
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/generate_format_image.py
cp .env.example .env
# Edit .env and set CLAY_WEBHOOK_URL (and CLAY_AUTH_TOKEN if you use auth)
streamlit run app.py
```

## CSV format

See the image on the upload page or download `assets/sample_template.csv`.

**Required:** Email, Company Domain Name, First Name, Last Name, Full Name  

**Optional:** Event Related Name, Outreach List Name, Contact or Company Owner, List Name, Accounting ERP Software  

Each submission gets a `list_id` (`000001`, `000002`, …) sent with every row to Clay.

## Testing with Clay

1. Create a Clay table with a **Webhook** source.
2. Finish **Setup mapping** so incoming JSON keys match your columns (use the same names as the CSV headers, plus `list_id`, `row_index`, `total_rows`).
3. Paste the webhook URL into `.env` as `CLAY_WEBHOOK_URL`.
4. Upload a 2–3 row test CSV in the app and confirm rows appear in Clay.

## Notes

- One HTTP POST per row (simplest for Clay webhooks).
- Submission history is stored in `data/submissions.db` locally.
- Do not commit `.env` or real webhook URLs.

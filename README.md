# Gmail Job Tracker App

This repository now includes a Python app (`job_tracker.py`) that scans your Gmail messages after a date and builds a job-application tracker with these statuses:

- `applied`
- `heard_back`
- `interview`
- `rejected`
- `pending`

It outputs:

- `job_tracker.csv` (spreadsheet-friendly tracker)
- `job_tracker_summary.json` (full structured summary)

## 1) Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

## 2) Create Gmail API credentials

1. Open Google Cloud Console.
2. Enable the **Gmail API** for your project.
3. Create an **OAuth client ID** for a desktop app.
4. Download the JSON file as `credentials.json` into this repo.

## 3) Run the tracker

```bash
python job_tracker.py --after 2024-02-01
```

Optional flags:

- `--credentials credentials.json`
- `--token token.json`
- `--out-csv job_tracker.csv`
- `--out-json job_tracker_summary.json`
- `--max-messages 3000`

On first run, your browser will open for Gmail OAuth approval.

## Notes

- The app searches across your Gmail messages (all labels/folders) after the date you provide.
- Classification is heuristic (pattern-based) and can be tuned in `STATUS_PATTERNS`.
- You can import `job_tracker.csv` into Google Sheets or Excel for filtering/sorting.

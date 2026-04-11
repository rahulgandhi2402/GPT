#!/usr/bin/env python3
"""Build a job-application tracker from Gmail messages.

This script reads Gmail messages after a supplied date, scans every label by
using the global message search endpoint, classifies job-application status,
and writes a tracker CSV + JSON summary.
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Iterable

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

STATUS_PATTERNS = {
    "rejected": [
        r"not moving forward",
        r"unfortunately",
        r"we regret to inform",
        r"position has been filled",
        r"decided to proceed with other candidates",
        r"rejection",
    ],
    "interview": [
        r"interview",
        r"interviewer",
        r"schedule.*(call|interview)",
        r"meet with",
        r"technical screen",
        r"onsite",
        r"final round",
    ],
    "heard_back": [
        r"thank you for applying",
        r"application received",
        r"next steps",
        r"assessment",
        r"follow up",
        r"update on your application",
        r"recruiter",
    ],
    "applied": [
        r"application submitted",
        r"applied",
        r"your application",
        r"we received your application",
        r"candidate portal",
    ],
}

SENDER_CLEAN = re.compile(r"<([^>]+)>")
COMPANY_STOPWORDS = {
    "jobs",
    "careers",
    "recruiting",
    "talent",
    "team",
    "notifications",
    "support",
    "mail",
    "noreply",
    "no-reply",
    "info",
    "hr",
    "hello",
}


@dataclass
class JobRecord:
    key: str
    company: str
    role_hint: str
    status: str
    confidence: float
    latest_date: str
    labels_seen: list[str]
    message_count: int
    examples: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a job tracker from Gmail messages after a date."
    )
    parser.add_argument(
        "--after",
        required=True,
        help="Only include messages after this date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--credentials",
        default="credentials.json",
        help="Path to OAuth client credentials JSON.",
    )
    parser.add_argument(
        "--token",
        default="token.json",
        help="Path to cached OAuth user token JSON.",
    )
    parser.add_argument(
        "--out-csv",
        default="job_tracker.csv",
        help="Output CSV path.",
    )
    parser.add_argument(
        "--out-json",
        default="job_tracker_summary.json",
        help="Output summary JSON path.",
    )
    parser.add_argument(
        "--max-messages",
        type=int,
        default=3000,
        help="Maximum number of messages to process.",
    )
    return parser.parse_args()


def validate_date(date_str: str) -> datetime:
    return datetime.strptime(date_str, "%Y-%m-%d")


def get_gmail_service(credentials_path: str, token_path: str):
    creds = None
    token_file = Path(token_path)
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        token_file.write_text(creds.to_json(), encoding="utf-8")

    return build("gmail", "v1", credentials=creds)


def list_message_ids(service, query: str, max_messages: int) -> list[str]:
    ids: list[str] = []
    next_page_token = None

    while len(ids) < max_messages:
        response = (
            service.users()
            .messages()
            .list(
                userId="me",
                q=query,
                includeSpamTrash=False,
                maxResults=min(500, max_messages - len(ids)),
                pageToken=next_page_token,
            )
            .execute()
        )
        ids.extend(message["id"] for message in response.get("messages", []))
        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    return ids[:max_messages]


def extract_headers(payload: dict) -> dict[str, str]:
    headers = {}
    for header in payload.get("headers", []):
        name = header.get("name", "").lower()
        value = header.get("value", "")
        headers[name] = value
    return headers


def extract_body_snippet(payload: dict) -> str:
    body_data = payload.get("body", {}).get("data")
    if body_data:
        decoded = base64.urlsafe_b64decode(body_data + "==")
        return decoded.decode("utf-8", errors="ignore")[:1200]

    for part in payload.get("parts", []):
        mime_type = part.get("mimeType", "")
        if mime_type.startswith("text/plain"):
            data = part.get("body", {}).get("data")
            if data:
                decoded = base64.urlsafe_b64decode(data + "==")
                return decoded.decode("utf-8", errors="ignore")[:1200]
    return ""


def normalize_sender(sender: str) -> str:
    match = SENDER_CLEAN.search(sender)
    email_addr = match.group(1) if match else sender
    email_addr = email_addr.strip().lower()
    return email_addr


def infer_company(sender: str) -> str:
    sender_email = normalize_sender(sender)
    domain = sender_email.split("@")[-1] if "@" in sender_email else sender_email
    parts = [p for p in domain.split(".") if p and p not in {"com", "io", "net", "org", "ai"}]
    clean_parts = [p for p in parts if p not in COMPANY_STOPWORDS]
    if not clean_parts:
        clean_parts = parts[:1]
    company = clean_parts[0] if clean_parts else sender_email
    return company.replace("-", " ").title()


def infer_role(subject: str) -> str:
    cleaned = re.sub(r"\s+", " ", subject).strip()
    cleaned = re.sub(r"^(re|fwd):\s*", "", cleaned, flags=re.I)
    return cleaned[:120]


def classify_status(text: str) -> tuple[str, float]:
    lowered = text.lower()
    for status in ["rejected", "interview", "heard_back", "applied"]:
        for pattern in STATUS_PATTERNS[status]:
            if re.search(pattern, lowered):
                score = 0.94 if status in {"rejected", "interview"} else 0.82
                return status, score
    return "pending", 0.4


def parse_datetime(date_header: str) -> datetime:
    try:
        return parsedate_to_datetime(date_header).astimezone()
    except Exception:
        return datetime.min.astimezone()


def fetch_job_messages(service, message_ids: Iterable[str]) -> list[dict]:
    rows = []
    for message_id in message_ids:
        message = (
            service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )
        payload = message.get("payload", {})
        headers = extract_headers(payload)
        subject = headers.get("subject", "")
        sender = headers.get("from", "")
        date_header = headers.get("date", "")
        snippet = message.get("snippet", "")
        body = extract_body_snippet(payload)

        merged_text = "\n".join([subject, snippet, body])
        status, confidence = classify_status(merged_text)
        sender_email = normalize_sender(sender)
        company = infer_company(sender)
        role_hint = infer_role(subject)
        date_obj = parse_datetime(date_header)

        key = f"{company.lower()}::{re.sub(r'[^a-z0-9]+', ' ', role_hint.lower()).strip()[:60]}"
        rows.append(
            {
                "key": key,
                "company": company,
                "sender": sender_email,
                "role_hint": role_hint,
                "status": status,
                "confidence": confidence,
                "date": date_obj,
                "date_iso": date_obj.isoformat(),
                "labels": message.get("labelIds", []),
                "subject": subject,
            }
        )
    return rows


def aggregate_records(rows: list[dict]) -> list[JobRecord]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["key"]].append(row)

    rank = {"rejected": 5, "interview": 4, "heard_back": 3, "applied": 2, "pending": 1}
    output: list[JobRecord] = []

    for key, items in grouped.items():
        items_sorted = sorted(items, key=lambda x: x["date"])
        latest = items_sorted[-1]
        best_status = sorted(items, key=lambda x: (rank[x["status"]], x["confidence"]))[-1]
        labels_seen = sorted({label for item in items for label in item["labels"]})
        examples = [item["subject"] for item in items_sorted[-3:] if item["subject"]]

        output.append(
            JobRecord(
                key=key,
                company=latest["company"],
                role_hint=latest["role_hint"],
                status=best_status["status"],
                confidence=round(best_status["confidence"], 2),
                latest_date=latest["date_iso"],
                labels_seen=labels_seen,
                message_count=len(items),
                examples=examples,
            )
        )

    return sorted(output, key=lambda r: (r.status, r.latest_date), reverse=True)


def write_csv(records: list[JobRecord], out_csv: str) -> None:
    fields = [
        "company",
        "role_hint",
        "status",
        "confidence",
        "latest_date",
        "message_count",
        "labels_seen",
        "examples",
    ]
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for record in records:
            row = asdict(record)
            writer.writerow(
                {
                    "company": row["company"],
                    "role_hint": row["role_hint"],
                    "status": row["status"],
                    "confidence": row["confidence"],
                    "latest_date": row["latest_date"],
                    "message_count": row["message_count"],
                    "labels_seen": ", ".join(row["labels_seen"]),
                    "examples": " | ".join(row["examples"]),
                }
            )


def write_summary(records: list[JobRecord], out_json: str, after_date: str) -> None:
    status_counts = Counter(record.status for record in records)
    summary = {
        "after_date": after_date,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "total_applications": len(records),
        "status_counts": dict(status_counts),
        "records": [asdict(record) for record in records],
    }
    Path(out_json).write_text(json.dumps(summary, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    validate_date(args.after)

    query = f"after:{args.after} (application OR recruiter OR interview OR career OR hiring OR reject OR offer)"
    service = get_gmail_service(args.credentials, args.token)
    message_ids = list_message_ids(service, query=query, max_messages=args.max_messages)

    rows = fetch_job_messages(service, message_ids)
    records = aggregate_records(rows)

    write_csv(records, args.out_csv)
    write_summary(records, args.out_json, args.after)

    counts = Counter(record.status for record in records)
    print(f"Processed {len(message_ids)} Gmail messages after {args.after}.")
    print(f"Tracker rows: {len(records)}")
    print("Status counts:", dict(counts))
    print(f"CSV: {args.out_csv}")
    print(f"JSON: {args.out_json}")


if __name__ == "__main__":
    main()

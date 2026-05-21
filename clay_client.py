from __future__ import annotations

import os
import time
from typing import Any

import pandas as pd
import requests


def get_webhook_url() -> str | None:
    return os.getenv("CLAY_WEBHOOK_URL", "").strip() or None


def get_auth_token() -> str | None:
    return os.getenv("CLAY_AUTH_TOKEN", "").strip() or None


def row_to_payload(
    row: pd.Series,
    list_id: str,
    row_index: int,
    total_rows: int,
    *,
    submitted_by: str = "",
    submission_list_name: str = "",
    record_type: str = "",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "list_id": list_id,
        "row_index": row_index,
        "total_rows": total_rows,
        "submitted_by": submitted_by,
        "submission_list_name": submission_list_name,
        "record_type": record_type,
    }
    for col, val in row.items():
        if pd.isna(val):
            payload[col] = ""
        else:
            payload[col] = str(val).strip()
    return payload


def send_rows_to_clay(
    df: pd.DataFrame,
    list_id: str,
    *,
    submitted_by: str = "",
    submission_list_name: str = "",
    record_type: str = "",
    batch_pause_sec: float = 0.05,
    timeout_sec: int = 30,
) -> tuple[int, list[str]]:
    """
    POST one row per request (Clay webhook default).
    Returns (success_count, error_messages).
    """
    url = get_webhook_url()
    if not url:
        return 0, ["CLAY_WEBHOOK_URL is not set. Add it to your .env file."]

    headers = {"Content-Type": "application/json"}
    token = get_auth_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    total = len(df)
    errors: list[str] = []
    success = 0

    for i, (_, row) in enumerate(df.iterrows(), start=1):
        payload = row_to_payload(
            row,
            list_id,
            i,
            total,
            submitted_by=submitted_by,
            submission_list_name=submission_list_name,
            record_type=record_type,
        )
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=timeout_sec)
            if resp.status_code >= 400:
                errors.append(f"Row {i}: HTTP {resp.status_code} — {resp.text[:200]}")
                if len(errors) >= 10:
                    errors.append("Stopping after 10 errors.")
                    break
                continue
            success += 1
        except requests.RequestException as e:
            errors.append(f"Row {i}: {e}")
            if len(errors) >= 10:
                errors.append("Stopping after 10 errors.")
                break

        if batch_pause_sec and i < total:
            time.sleep(batch_pause_sec)

    return success, errors

from __future__ import annotations

import pandas as pd

from config import ALL_HEADERS, HEADER_ALIASES, OPTIONAL_HEADERS, REQUIRED_HEADERS


def _normalize_key(name: str) -> str:
    return str(name).strip().lower().replace("_", " ")


def normalize_columns(df: pd.DataFrame) -> tuple[pd.DataFrame | None, list[str]]:
    """Rename columns to canonical headers. Returns (df, errors)."""
    errors: list[str] = []
    rename_map: dict[str, str] = {}
    seen_canonical: set[str] = set()

    for col in df.columns:
        key = _normalize_key(col)
        canonical = HEADER_ALIASES.get(key)
        if canonical is None:
            # Try exact match on canonical display names
            for h in ALL_HEADERS:
                if _normalize_key(h) == key:
                    canonical = h
                    break
        if canonical is None:
            errors.append(f"Unknown column: '{col}'")
            continue
        if canonical in seen_canonical:
            errors.append(f"Duplicate column maps to '{canonical}'")
            continue
        rename_map[col] = canonical
        seen_canonical.add(canonical)

    missing = [h for h in REQUIRED_HEADERS if h not in seen_canonical]
    if missing:
        errors.extend([f"Missing required column: {h}" for h in missing])

    if errors:
        return None, errors

    out = df.rename(columns=rename_map)
    for h in OPTIONAL_HEADERS:
        if h not in out.columns:
            out[h] = ""
    out = out[ALL_HEADERS]
    return out, []


def validate_rows(df: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    for idx, row in df.iterrows():
        row_num = int(idx) + 2  # header is row 1
        email = str(row.get("Email", "")).strip()
        domain = str(row.get("Company Domain Name", "")).strip()
        first = str(row.get("First Name", "")).strip()
        last = str(row.get("Last Name", "")).strip()
        full = str(row.get("Full Name", "")).strip()

        if not email:
            errors.append(f"Row {row_num}: Email is required")
        if not domain:
            errors.append(f"Row {row_num}: Company Domain Name is required")
        if not first:
            errors.append(f"Row {row_num}: First Name is required")
        if not last:
            errors.append(f"Row {row_num}: Last Name is required")
        if not full:
            errors.append(f"Row {row_num}: Full Name is required")

        if len(errors) >= 25:
            errors.append("…and more row errors (fix required fields first)")
            break
    return errors

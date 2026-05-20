"""CSV ingestion + validation for List Enrichment Dropbox."""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field

import pandas as pd

from config import (
    ALL_HEADERS,
    EXPECTED_HEADERS,
    HEADER_ALIASES,
    NAME_HEADERS,
    OPTIONAL_HEADERS,
    REQUIRED_HEADERS,
)

_MAX_ROWS = 50_000
_MAX_ROW_ERRORS_SHOWN = 25
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_DOMAIN_RE = re.compile(
    r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.[A-Za-z0-9-]{1,63})+$"
)


@dataclass
class ValidationResult:
    df: pd.DataFrame | None = None
    column_errors: list[str] = field(default_factory=list)
    row_errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    unknown_columns: list[str] = field(default_factory=list)
    missing_required: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.column_errors and not self.row_errors


def _normalize_key(name: str) -> str:
    return str(name).strip().lstrip("\ufeff").lower().replace("_", " ")


def _sniff_delimiter(sample: str) -> str:
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        return dialect.delimiter
    except csv.Error:
        return ","


def read_csv_safely(file_bytes: bytes) -> tuple[pd.DataFrame | None, list[str]]:
    """Try multiple encodings and delimiters. Returns (df, errors)."""
    errors: list[str] = []
    encodings = ["utf-8-sig", "utf-8", "latin-1"]

    text: str | None = None
    for enc in encodings:
        try:
            text = file_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        return None, [
            "We couldn't decode the file. Make sure it's saved as a CSV "
            "(UTF-8 recommended)."
        ]

    sample = text[:4096]
    delimiter = _sniff_delimiter(sample)
    if delimiter != ",":
        errors.append(
            f"Your file appears to use `{delimiter!r}` as the separator. "
            "Please re-save as a comma-separated CSV."
        )
        return None, errors

    try:
        df = pd.read_csv(
            io.StringIO(text),
            dtype=str,
            skip_blank_lines=True,
            keep_default_na=False,
        )
    except Exception as e:
        return None, [f"We couldn't parse the CSV: {e}"]

    df.columns = [str(c).strip().lstrip("\ufeff") for c in df.columns]
    df = df.dropna(how="all")
    df = df[~(df.astype(str).apply(lambda s: s.str.strip()).eq("").all(axis=1))]
    df = df.reset_index(drop=True)

    if df.empty:
        return None, ["The CSV has headers but no data rows."]

    return df, []


def normalize_columns(df: pd.DataFrame) -> tuple[pd.DataFrame | None, ValidationResult]:
    """Rename to canonical headers and validate column set."""
    result = ValidationResult()
    rename_map: dict[str, str] = {}
    seen_canonical: set[str] = set()
    unknown: list[str] = []
    duplicates: list[tuple[str, str]] = []

    canonical_lookup = {_normalize_key(h): h for h in ALL_HEADERS}

    for col in df.columns:
        key = _normalize_key(col)
        canonical = HEADER_ALIASES.get(key) or canonical_lookup.get(key)
        if canonical is None:
            unknown.append(col)
            continue
        if canonical in seen_canonical:
            duplicates.append((col, canonical))
            continue
        rename_map[col] = canonical
        seen_canonical.add(canonical)

    missing = [h for h in EXPECTED_HEADERS if h not in seen_canonical]
    result.missing_required = missing
    result.unknown_columns = unknown

    if missing:
        result.column_errors.append(
            "Missing required column(s): " + ", ".join(f"`{h}`" for h in missing)
        )
    if unknown:
        result.column_errors.append(
            "Unknown column(s): " + ", ".join(f"`{c}`" for c in unknown)
            + " — column names must match the format exactly."
        )
    if duplicates:
        for col, can in duplicates:
            result.column_errors.append(
                f"Column `{col}` maps to `{can}`, which was already provided. "
                "Remove the duplicate."
            )

    if result.column_errors:
        return None, result

    out = df.rename(columns=rename_map)
    for h in OPTIONAL_HEADERS:
        if h not in out.columns:
            out[h] = ""
    out = out[ALL_HEADERS].copy()
    for c in out.columns:
        out[c] = out[c].astype(str).str.strip()

    result.df = out
    return out, result


def _looks_like_email(s: str) -> bool:
    return bool(_EMAIL_RE.match(s))


def _looks_like_domain(s: str) -> bool:
    return bool(_DOMAIN_RE.match(s)) and "@" not in s


def validate_rows(df: pd.DataFrame) -> list[str]:
    """Validate per-row and backfill Full Name from First+Last when possible.

    Mutates df in place to fill Full Name when only First+Last are provided.
    """
    errors: list[str] = []
    truncated = False

    for idx, row in df.iterrows():
        row_num = int(idx) + 2  # +1 for 1-indexed, +1 for header row
        email = row["Email"]
        domain = row["Company Domain Name"]
        first = row["First Name"]
        last = row["Last Name"]
        full = row["Full Name"]

        missing_fields = []
        if not email:
            missing_fields.append("Email")
        if not domain:
            missing_fields.append("Company Domain Name")
        if missing_fields:
            errors.append(
                f"Row {row_num}: missing required field(s): "
                + ", ".join(missing_fields)
            )

        has_full = bool(full)
        has_first_last = bool(first) and bool(last)
        if not has_full and not has_first_last:
            errors.append(
                f"Row {row_num}: provide either `Full Name` OR both "
                "`First Name` and `Last Name`."
            )
        elif not has_full and has_first_last:
            df.at[idx, "Full Name"] = f"{first} {last}".strip()

        if email and not _looks_like_email(email):
            errors.append(f"Row {row_num}: Email `{email}` is not a valid email address.")
        if domain and not _looks_like_domain(domain):
            errors.append(
                f"Row {row_num}: Company Domain Name `{domain}` does not look like a "
                "domain (e.g. `acme.com`, not `https://acme.com` or `john@acme.com`)."
            )

        if len(errors) >= _MAX_ROW_ERRORS_SHOWN:
            truncated = True
            break

    if truncated:
        errors.append(
            f"...and more issues below. Showing first {_MAX_ROW_ERRORS_SHOWN}. "
            "Fix these and re-upload to see anything else."
        )

    return errors


def validate_upload(file_bytes: bytes) -> ValidationResult:
    """One-shot end-to-end CSV validation."""
    result = ValidationResult()

    df, read_errors = read_csv_safely(file_bytes)
    if read_errors:
        result.column_errors.extend(read_errors)
        return result
    assert df is not None

    if len(df) > _MAX_ROWS:
        result.column_errors.append(
            f"CSV has {len(df):,} rows; the maximum allowed per upload is "
            f"{_MAX_ROWS:,}. Split the list and try again."
        )
        return result

    normalized, col_result = normalize_columns(df)
    if col_result.column_errors:
        return col_result

    assert normalized is not None
    row_errors = validate_rows(normalized)
    col_result.row_errors = row_errors
    return col_result

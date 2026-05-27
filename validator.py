"""CSV ingestion + validation for List Enrichment Dropbox."""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field

import pandas as pd

from config import (
    COMPANY_ALL_HEADERS,
    CONTACT_ALL_HEADERS,
    HEADER_ALIASES,
    LIST_TYPE_COMPANY,
    LIST_TYPE_CONTACTS,
    RECORD_TYPES,
    all_headers_for,
    name_headers_for,
    optional_headers_for,
    required_headers_for,
)

_MAX_ROWS = 50_000
_MAX_ROW_ERRORS_SHOWN = 25
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
# Accept either a raw domain (acme.com, www.acme.co.uk) OR a full URL
# (https://acme.com, http://www.acme.com/path). Anything with at least
# one dot, no @, no whitespace, and a recognizable TLD-ish ending works.
_DOMAIN_OR_URL_RE = re.compile(
    r"^(?:https?://)?"           # optional scheme
    r"(?:[A-Za-z0-9-]+\.)+"      # one or more "label." segments
    r"[A-Za-z]{2,}"              # TLD (2+ letters)
    r"(?:[:/?#].*)?$",           # optional port/path/query/fragment
    re.IGNORECASE,
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


def _detect_list_type_mismatch(headers: list[str], list_type: str) -> str | None:
    """If the CSV's columns clearly belong to the OTHER list type, return a hint.

    The hint is rendered as HTML inside the validation error block, so light
    inline tags (<b>, <code>) are intentional.
    """
    normalized = {_normalize_key(h) for h in headers}
    canonical_lookup = {
        _normalize_key(h): h for h in CONTACT_ALL_HEADERS + COMPANY_ALL_HEADERS
    }
    canonical_present: set[str] = set()
    for n in normalized:
        canonical = HEADER_ALIASES.get(n) or canonical_lookup.get(n)
        if canonical:
            canonical_present.add(canonical)

    contact_signals = {"Email", "First Name", "Last Name", "Full Name", "Contact Owner"}
    contact_offenders = canonical_present & contact_signals

    if list_type == LIST_TYPE_COMPANY and contact_offenders:
        offender_str = ", ".join(
            f"<code>{h}</code>" for h in sorted(contact_offenders)
        )
        return (
            f"<b>This looks like a Contact list, not a Company list.</b> "
            f"Your CSV includes {offender_str}, which only belong on contact lists. "
            f"Switch <b>List type</b> above to <b>Contacts</b> and re-upload, or "
            f"remove these columns if you really meant a company-only list."
        )

    if list_type == LIST_TYPE_CONTACTS:
        company_required = {"Company Domain Name", "Record Type", "Company Name"}
        if (
            company_required.issubset(canonical_present)
            and not (canonical_present & contact_signals)
        ):
            return (
                "<b>This looks like a Company list, not a Contact list.</b> "
                "Your CSV has the company columns (<code>Company Domain Name</code>, "
                "<code>Record Type</code>, <code>Company Name</code>) but no "
                "<code>Email</code> or name columns for individual contacts. "
                "Switch <b>List type</b> above to <b>Companies</b> and re-upload."
            )

    return None


def normalize_columns(
    df: pd.DataFrame, list_type: str
) -> tuple[pd.DataFrame | None, ValidationResult]:
    """Rename to canonical headers and validate column set."""
    result = ValidationResult()

    # Catch wrong-list-type early so the user gets a clear nudge before the
    # generic "Unknown column" errors pile up.
    mismatch_hint = _detect_list_type_mismatch(list(df.columns), list_type)
    if mismatch_hint:
        result.column_errors.append(mismatch_hint)
        return None, result

    rename_map: dict[str, str] = {}
    seen_canonical: set[str] = set()
    unknown: list[str] = []
    duplicates: list[tuple[str, str]] = []

    required = required_headers_for(list_type)
    name_headers = name_headers_for(list_type)
    optional_headers = optional_headers_for(list_type)
    all_headers = all_headers_for(list_type)
    allowed_set = set(all_headers)

    canonical_lookup = {_normalize_key(h): h for h in all_headers}

    for col in df.columns:
        key = _normalize_key(col)
        canonical = HEADER_ALIASES.get(key) or canonical_lookup.get(key)
        if canonical is None or canonical not in allowed_set:
            unknown.append(col)
            continue
        if canonical in seen_canonical:
            duplicates.append((col, canonical))
            continue
        rename_map[col] = canonical
        seen_canonical.add(canonical)

    missing = [h for h in required if h not in seen_canonical]
    result.missing_required = missing
    result.unknown_columns = unknown

    if missing:
        result.column_errors.append(
            "Missing required column(s): " + ", ".join(f"`{h}`" for h in missing)
        )

    if list_type == LIST_TYPE_CONTACTS:
        has_full_col = "Full Name" in seen_canonical
        has_first_col = "First Name" in seen_canonical
        has_last_col = "Last Name" in seen_canonical
        if not has_full_col and not (has_first_col and has_last_col):
            result.column_errors.append(
                "Missing name column(s): include either a `Full Name` column "
                "OR both `First Name` and `Last Name` columns."
            )

    if unknown:
        result.column_errors.append(
            "Unknown column(s): " + ", ".join(f"`{c}`" for c in unknown)
            + " — column names must match the format exactly for this list type."
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
    for h in name_headers + optional_headers:
        if h not in out.columns:
            out[h] = ""
    out = out[all_headers].copy()
    for c in out.columns:
        out[c] = out[c].astype(str).str.strip()

    result.df = out
    return out, result


def _looks_like_email(s: str) -> bool:
    return bool(_EMAIL_RE.match(s))


def _looks_like_domain_or_url(s: str) -> bool:
    if "@" in s or " " in s:
        return False
    return bool(_DOMAIN_OR_URL_RE.match(s))


def _split_full_name(full: str) -> tuple[str, str]:
    """Split 'First Middle Last' into (first, last).

    Heuristic: first word is first name, the rest joined is last name.
    Returns ("", "") if not splittable.
    """
    parts = full.split()
    if len(parts) == 0:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def _validate_record_type(
    df: pd.DataFrame,
    idx: int,
    row_num: int,
    record_type: str,
    record_type_lookup: dict[str, str],
    allowed_list: str,
    errors: list[str],
) -> None:
    canonical = record_type_lookup.get(record_type.strip().lower())
    if canonical is None:
        errors.append(
            f"Row {row_num}: Record Type `{record_type}` is not allowed. "
            f"Must be one of {allowed_list}."
        )
    else:
        df.at[idx, "Record Type"] = canonical


def _validate_domain(
    row_num: int, domain: str, errors: list[str]
) -> None:
    if domain and not _looks_like_domain_or_url(domain):
        errors.append(
            f"Row {row_num}: Company Domain Name `{domain}` does not look like a "
            "domain or website (e.g. `acme.com` or `https://acme.com`, "
            "not `john@acme.com`)."
        )


def _validate_owner_email(
    row_num: int, field_label: str, value: str, errors: list[str]
) -> None:
    """Owner fields are optional, but when present must be a HubSpot user email."""
    if value and not _looks_like_email(value):
        errors.append(
            f"Row {row_num}: {field_label} `{value}` must be a HubSpot user email "
            "(e.g. `claurits@paystand.com`), not a name. Leave blank if you "
            "don't know it."
        )


def validate_rows(df: pd.DataFrame, list_type: str) -> list[str]:
    """Per-row validation.

    For contact lists, also backfills name fields when possible (Full Name from
    First+Last, or First/Last from Full Name).
    """
    errors: list[str] = []
    truncated = False
    record_type_lookup = {rt.lower(): rt for rt in RECORD_TYPES}
    allowed_list = ", ".join(f"`{rt}`" for rt in RECORD_TYPES)

    for idx, row in df.iterrows():
        row_num = int(idx) + 2  # +1 for 1-indexed, +1 for header row
        domain = row["Company Domain Name"]
        record_type = row["Record Type"]

        if list_type == LIST_TYPE_COMPANY:
            company_name = row["Company Name"]
            company_owner = row.get("Company Owner", "")
            missing_fields = []
            if not domain:
                missing_fields.append("Company Domain Name")
            if not record_type:
                missing_fields.append("Record Type")
            if not company_name:
                missing_fields.append("Company Name")
            if missing_fields:
                errors.append(
                    f"Row {row_num}: missing required field(s): "
                    + ", ".join(missing_fields)
                )

            if record_type:
                _validate_record_type(
                    df, idx, row_num, record_type, record_type_lookup,
                    allowed_list, errors,
                )
            _validate_domain(row_num, domain, errors)
            _validate_owner_email(row_num, "Company Owner", company_owner, errors)

        else:  # Contact list
            email = row["Email"]
            first = row["First Name"]
            last = row["Last Name"]
            full = row["Full Name"]

            missing_fields = []
            if not email:
                missing_fields.append("Email")
            if not domain:
                missing_fields.append("Company Domain Name")
            if not record_type:
                missing_fields.append("Record Type")
            if missing_fields:
                errors.append(
                    f"Row {row_num}: missing required field(s): "
                    + ", ".join(missing_fields)
                )

            if record_type:
                _validate_record_type(
                    df, idx, row_num, record_type, record_type_lookup,
                    allowed_list, errors,
                )

            if full and (not first or not last):
                split_first, split_last = _split_full_name(full)
                if not first and split_first:
                    df.at[idx, "First Name"] = split_first
                    first = split_first
                if not last and split_last:
                    df.at[idx, "Last Name"] = split_last
                    last = split_last

            if not full and first and last:
                df.at[idx, "Full Name"] = f"{first} {last}".strip()
                full = f"{first} {last}".strip()

            has_full = bool(full)
            has_first_last = bool(first) and bool(last)
            if not has_full and not has_first_last:
                errors.append(
                    f"Row {row_num}: provide either `Full Name` OR both "
                    "`First Name` and `Last Name`."
                )

            if email and not _looks_like_email(email):
                errors.append(
                    f"Row {row_num}: Email `{email}` is not a valid email address."
                )
            _validate_domain(row_num, domain, errors)
            _validate_owner_email(
                row_num, "Contact Owner", row.get("Contact Owner", ""), errors,
            )
            _validate_owner_email(
                row_num, "Company Owner", row.get("Company Owner", ""), errors,
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


def validate_upload(
    file_bytes: bytes, list_type: str = LIST_TYPE_CONTACTS
) -> ValidationResult:
    """One-shot end-to-end CSV validation for the given list type."""
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

    normalized, col_result = normalize_columns(df, list_type)
    if col_result.column_errors:
        return col_result

    assert normalized is not None
    row_errors = validate_rows(normalized, list_type)
    col_result.row_errors = row_errors
    return col_result

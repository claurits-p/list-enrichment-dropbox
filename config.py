"""Column schema for List Enrichment Dropbox."""

# ---------------------------------------------------------------------------
# List types
# ---------------------------------------------------------------------------

LIST_TYPE_CONTACTS = "Contacts"
LIST_TYPE_COMPANY = "Companies"
LIST_TYPES = (LIST_TYPE_CONTACTS, LIST_TYPE_COMPANY)


# ---------------------------------------------------------------------------
# Contact list schema
# ---------------------------------------------------------------------------

# Always required (per row) — contact lists
CONTACT_REQUIRED_HEADERS = [
    "Email",
    "Company Domain Name",
    "Record Type",
]

# Headers about the person's name. CSV must include columns such that EITHER
# Full Name is present OR both First Name + Last Name are present.
CONTACT_NAME_HEADERS = [
    "First Name",
    "Last Name",
    "Full Name",
]

CONTACT_OPTIONAL_HEADERS = [
    "Company Name",
    "Event Related Name",
    "Outreach List Name",
    "Contact Owner",
    "Company Owner",
    "Accounting ERP Software",
]

CONTACT_ALL_HEADERS = (
    CONTACT_REQUIRED_HEADERS + CONTACT_NAME_HEADERS + CONTACT_OPTIONAL_HEADERS
)


# ---------------------------------------------------------------------------
# Company list schema
# ---------------------------------------------------------------------------

# Always required (per row) — company lists
COMPANY_REQUIRED_HEADERS = [
    "Company Domain Name",
    "Record Type",
    "Company Name",
]

COMPANY_OPTIONAL_HEADERS = [
    "Event Related Name",
    "Outreach List Name",
    "Company Owner",
    "Accounting ERP Software",
]

COMPANY_ALL_HEADERS = COMPANY_REQUIRED_HEADERS + COMPANY_OPTIONAL_HEADERS

# Header label shown to users in the company-list template. The canonical
# internal name remains "Company Domain Name" (and aliases keep both working).
COMPANY_DOMAIN_DISPLAY_HEADER = "Website"


# ---------------------------------------------------------------------------
# Per-list-type accessors
# ---------------------------------------------------------------------------

def required_headers_for(list_type: str) -> list[str]:
    if list_type == LIST_TYPE_COMPANY:
        return list(COMPANY_REQUIRED_HEADERS)
    return list(CONTACT_REQUIRED_HEADERS)


def name_headers_for(list_type: str) -> list[str]:
    if list_type == LIST_TYPE_COMPANY:
        return []
    return list(CONTACT_NAME_HEADERS)


def optional_headers_for(list_type: str) -> list[str]:
    if list_type == LIST_TYPE_COMPANY:
        return list(COMPANY_OPTIONAL_HEADERS)
    return list(CONTACT_OPTIONAL_HEADERS)


def all_headers_for(list_type: str) -> list[str]:
    if list_type == LIST_TYPE_COMPANY:
        return list(COMPANY_ALL_HEADERS)
    return list(CONTACT_ALL_HEADERS)


def expected_headers_for(list_type: str) -> list[str]:
    """Headers that must exist in the CSV (their values may be conditionally optional)."""
    return required_headers_for(list_type) + name_headers_for(list_type)


# ---------------------------------------------------------------------------
# Legacy aliases (still consumed by some scripts) — default to contact schema
# ---------------------------------------------------------------------------

REQUIRED_HEADERS = CONTACT_REQUIRED_HEADERS
NAME_HEADERS = CONTACT_NAME_HEADERS
OPTIONAL_HEADERS = CONTACT_OPTIONAL_HEADERS
EXPECTED_HEADERS = CONTACT_REQUIRED_HEADERS + CONTACT_NAME_HEADERS
ALL_HEADERS = CONTACT_ALL_HEADERS


# ---------------------------------------------------------------------------
# Header aliases — normalize common variations to canonical names
# ---------------------------------------------------------------------------

HEADER_ALIASES = {
    "email": "Email",
    "email address": "Email",
    "company domain": "Company Domain Name",
    "company domain name": "Company Domain Name",
    "domain": "Company Domain Name",
    "domain name": "Company Domain Name",
    "website": "Company Domain Name",
    "company website": "Company Domain Name",
    "company url": "Company Domain Name",
    "url": "Company Domain Name",
    "site": "Company Domain Name",
    "first name": "First Name",
    "first_name": "First Name",
    "firstname": "First Name",
    "last name": "Last Name",
    "last_name": "Last Name",
    "lastname": "Last Name",
    "full name": "Full Name",
    "full_name": "Full Name",
    "fullname": "Full Name",
    "company name": "Company Name",
    "company_name": "Company Name",
    "companyname": "Company Name",
    "company": "Company Name",
    "organization": "Company Name",
    "organization name": "Company Name",
    "org": "Company Name",
    "account name": "Company Name",
    "event related name": "Event Related Name",
    "event_related_name": "Event Related Name",
    "outreach list name": "Outreach List Name",
    "outreach_list_name": "Outreach List Name",
    "contact owner": "Contact Owner",
    "contact_owner": "Contact Owner",
    "company owner": "Company Owner",
    "company_owner": "Company Owner",
    "accounting erp software": "Accounting ERP Software",
    "accounting_erp_software": "Accounting ERP Software",
    "erp": "Accounting ERP Software",
    "record type": "Record Type",
    "record_type": "Record Type",
    "type": "Record Type",
    "contact type": "Record Type",
}


# ---------------------------------------------------------------------------
# App-wide constants
# ---------------------------------------------------------------------------

APP_TITLE = "List Enrichment Dropbox"
DATA_DIR = "data"
DB_PATH = f"{DATA_DIR}/submissions.db"

# Lists with more rows than this need admin approval. Company lists fan out via
# ZI "Find Contacts", so each company row can become many contact rows — the
# threshold for that type is set much lower.
LARGE_LIST_THRESHOLDS = {
    LIST_TYPE_CONTACTS: 1000,
    LIST_TYPE_COMPANY: 100,
}

LARGE_LIST_THRESHOLD = LARGE_LIST_THRESHOLDS[LIST_TYPE_CONTACTS]  # legacy


def threshold_for(list_type: str) -> int:
    return LARGE_LIST_THRESHOLDS.get(
        list_type, LARGE_LIST_THRESHOLDS[LIST_TYPE_CONTACTS]
    )


# Allowed Record Type values (per row in both list types)
RECORD_TYPES = ("Prospect", "Partner", "Competitor")

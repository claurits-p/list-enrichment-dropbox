"""Column schema for List Enrichment Dropbox."""

# Canonical CSV headers (exact spelling users should use)
REQUIRED_HEADERS = [
    "Email",
    "Company Domain Name",
    "First Name",
    "Last Name",
    "Full Name",
]

OPTIONAL_HEADERS = [
    "Event Related Name",
    "Outreach List Name",
    "Contact Owner",
    "Company Owner",
    "List Name",
    "Accounting ERP Software",
]

ALL_HEADERS = REQUIRED_HEADERS + OPTIONAL_HEADERS

# Normalize common variations to canonical names
HEADER_ALIASES = {
    "email": "Email",
    "company domain": "Company Domain Name",
    "company domain name": "Company Domain Name",
    "domain": "Company Domain Name",
    "company_domain": "Company Domain Name",
    "company_domain_name": "Company Domain Name",
    "first name": "First Name",
    "first_name": "First Name",
    "firstname": "First Name",
    "last name": "Last Name",
    "last_name": "Last Name",
    "lastname": "Last Name",
    "full name": "Full Name",
    "full_name": "Full Name",
    "fullname": "Full Name",
    "event related name": "Event Related Name",
    "event_related_name": "Event Related Name",
    "outreach list name": "Outreach List Name",
    "outreach_list_name": "Outreach List Name",
    "contact owner": "Contact Owner",
    "contact_owner": "Contact Owner",
    "company owner": "Company Owner",
    "company_owner": "Company Owner",
    "list name": "List Name",
    "list_name": "List Name",
    "accounting erp software": "Accounting ERP Software",
    "accounting_erp_software": "Accounting ERP Software",
    "erp": "Accounting ERP Software",
}

APP_TITLE = "List Enrichment Dropbox"
DATA_DIR = "data"
DB_PATH = f"{DATA_DIR}/submissions.db"

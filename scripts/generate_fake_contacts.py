"""Generate a fake-contacts CSV for testing the upload flow."""

import csv
import random
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent.parent / "test_300_contacts.csv"

FIRST_NAMES = [
    "Paul", "Janet", "Michelle", "Rebecca", "Jim", "Caitlin", "Rowan", "Shana",
    "Lindsay", "Jenna", "Zachary", "Sheilya", "Timothy", "William", "Chris",
    "Ryan", "Kristen", "Arlene", "David", "Keithana", "Judi", "Andrew", "Eric",
    "Tj", "Cathy", "Benjamin", "Maria", "Jose", "Aisha", "Carlos", "Priya",
    "Olivia", "Noah", "Liam", "Emma", "Sophia", "Mason", "Ava", "Lucas",
    "Mia", "Ethan", "Isabella", "Logan", "Charlotte", "James", "Amelia",
    "Benjamin", "Harper", "Elijah", "Evelyn", "Henry", "Abigail", "Sebastian",
    "Emily", "Jackson", "Elizabeth", "Aiden", "Sofia", "Matthew", "Madison",
    "Samuel", "Avery", "Joseph", "Ella", "Daniel", "Scarlett", "Owen", "Grace",
    "Wyatt", "Chloe", "John", "Victoria", "Dylan", "Riley", "Luke", "Aria",
    "Gabriel", "Lily", "Anthony", "Aubrey", "Isaac", "Zoey", "Grayson",
    "Penelope", "Jack", "Lillian", "Julian", "Addison", "Levi", "Layla",
    "Christopher", "Natalie", "Joshua", "Camila", "Andrew", "Hannah", "Lincoln",
    "Brooklyn", "Mateo", "Zoe", "Ryan", "Nora", "Jaxon", "Leah", "Nathan",
    "Savannah", "Aaron", "Audrey", "Adrian", "Claire", "Hunter", "Eleanor",
    "Christian", "Skylar", "Connor", "Ellie", "Eli", "Samantha", "Easton",
    "Stella", "Cameron", "Paisley",
]

LAST_NAMES = [
    "Bowker", "Thompson", "Goodwin", "Gabor", "Stephenson", "Higgins", "Benjamin",
    "Rowlette", "Keller", "Williams", "Walters", "Swan", "Newville", "Tempone",
    "Da Silva", "Benton", "Stillwell", "Talbot", "Peoples", "Senthilnathan",
    "Reed", "Claude", "Jaschke", "Shah", "Mullins", "Lee", "Smith", "Johnson",
    "Brown", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez",
    "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore",
    "Jackson", "Martin", "Lee", "Perez", "White", "Harris", "Sanchez", "Clark",
    "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen", "King", "Wright",
    "Scott", "Torres", "Nguyen", "Hill", "Flores", "Green", "Adams", "Nelson",
    "Baker", "Hall", "Rivera", "Campbell", "Mitchell", "Carter", "Roberts",
    "Patel", "Gomez", "Phillips", "Evans", "Turner", "Diaz", "Parker", "Cruz",
    "Edwards", "Collins", "Reyes", "Stewart", "Morris", "Morales", "Murphy",
    "Cook", "Rogers", "Gutierrez", "Ortiz", "Morgan", "Cooper", "Peterson",
    "Bailey", "Reed", "Kelly", "Howard", "Ramos", "Kim", "Cox", "Ward",
]

COMPANY_BASES = [
    "creeks", "arthritis", "magswitch", "allstateider", "rpmmoves", "sovrn",
    "vestmark", "mannlakeltd", "veritacorp", "indinero", "acftechnology",
    "saluteinc", "arenaco", "transnetyx", "hartbeat", "enovix", "expertvoice",
    "airportappliance", "ultimagenomics", "compassdatacenters", "velocitymsc",
    "nalumed", "valiant-als", "bugcrowd", "donyati", "fintech-labs",
    "bluemarble", "cyberspark", "datasphere", "echoworks", "fusionpath",
    "greenleaf", "harborlight", "ironpoint", "jadewave", "kestrel-systems",
    "lumecraft", "metanorth", "novaqore", "obsidian-tech", "polarisai",
    "quantumforge", "redshift-ai", "saltlake-saas", "tidalbase", "ursacorp",
    "vortex-cloud", "waveform", "xenonworks", "yondrlabs", "zenithops",
    "alphagrid", "beacon-pay", "cascadefin", "deltaforge", "evergreen-bio",
    "flashfire", "globalrise", "horizonpath", "indigopay", "junipernet",
    "kineticops", "lumosfin", "metroclear", "northstar-it", "opalcore",
    "primaryfn", "questaisha", "ridgewave", "stellargrid", "trustworth",
    "ulmeridian", "vanguard-stack", "wildcatpay", "xerusio", "yellowstone-bi",
    "zephyrcorp",
]

TLDS = ["com", "io", "co", "ai", "net", "org", "co.uk", "tech", "app", "dev"]

# A few websites use full URL format to test that the validator accepts both.
URL_PREFIXES = ["", "", "", "", "www.", "https://", "https://www.", "http://"]

random.seed(42)


def _company_name_from_base(base: str) -> str:
    """Turn a domain base like 'fintech-labs' into 'Fintech Labs'."""
    return " ".join(part.capitalize() for part in base.replace("-", " ").split())


def main(n: int = 300) -> None:
    headers = [
        "First Name",
        "Last Name",
        "Website",
        "Email Address",
        "Record Type",
        "Company Name",
        "Event Related Name",
        "Outreach List Name",
        "Accounting ERP Software",
    ]
    record_types = ["Prospect", "Prospect", "Prospect", "Partner", "Competitor"]
    erp_options = [
        "", "", "", "", "", "NetSuite", "QuickBooks", "Sage Intacct",
        "Microsoft Dynamics", "Acumatica", "SAP", "Xero",
    ]
    events = [
        "", "", "", "", "Q2 Webinar", "Spring Summit", "Partner Roadshow",
        "ICP Discovery Series", "Finance Leaders Forum",
    ]
    outreach = [
        "", "", "", "Outbound May", "ABM Tier 1", "Event Followup Q2",
        "ICP Discovery", "Top 500 Mid-Market",
    ]
    company_suffixes = ["", "", " Inc.", " LLC", " Corp", ", Inc.", " Group"]

    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for _ in range(n):
            first = random.choice(FIRST_NAMES)
            last = random.choice(LAST_NAMES)
            base = random.choice(COMPANY_BASES)
            tld = random.choice(TLDS)
            domain = f"{base}.{tld}"
            prefix = random.choice(URL_PREFIXES)
            website = f"{prefix}{domain}"
            email_local = f"{first}.{last}".lower().replace(" ", "")
            email = f"{email_local}@{domain}"

            # ~25% of rows leave Company Name blank to exercise the optional path.
            if random.random() < 0.25:
                company_name = ""
            else:
                company_name = (
                    _company_name_from_base(base) + random.choice(company_suffixes)
                )

            writer.writerow([
                first,
                last,
                website,
                email,
                random.choice(record_types),
                company_name,
                random.choice(events),
                random.choice(outreach),
                random.choice(erp_options),
            ])

    print(f"Wrote {n} rows to {OUT}")


if __name__ == "__main__":
    main()

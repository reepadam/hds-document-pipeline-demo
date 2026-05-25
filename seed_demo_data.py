"""
One-shot seed script to populate the demo with HDS-relevant customers,
mocked Antera jobs per customer, and a few sample accepted orders so
the Customer Library and Reporting pages don't look empty during the demo.

Run once: python seed_demo_data.py
Idempotent - won't duplicate customers that already exist.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import customer_repo as repo


# Real HDS clients pulled from hdsbrands.com homepage + sports vertical
HDS_CUSTOMERS = [
    # NFL / sports (HDS Sports vertical)
    {"display_name": "Pittsburgh Steelers", "antera_id": "CUS-STL-001", "notes": "NFL — local hometown account; high-volume merch + uniform program"},
    {"display_name": "Cleveland Cavaliers", "antera_id": "CUS-CLE-002", "notes": "NBA — Northeast Ohio account"},
    {"display_name": "Arizona Cardinals", "antera_id": "CUS-ARI-003", "notes": "NFL — fan merch + sideline gear"},
    {"display_name": "Denver Broncos", "antera_id": "CUS-DEN-004", "notes": "NFL — uniform program + team store"},
    {"display_name": "New England Patriots", "antera_id": "CUS-NEP-005", "notes": "NFL — team store SKUs + season giveaways"},
    {"display_name": "NFL (league office)", "antera_id": "CUS-NFL-006", "notes": "League-level promotional + draft event merch"},
    # Pittsburgh corporate
    {"display_name": "Highmark", "antera_id": "CUS-HMK-010", "notes": "Healthcare — employee uniform program + wellness boxes"},
    {"display_name": "Allegheny Health Network (AHN)", "antera_id": "CUS-AHN-011", "notes": "Health system — branded apparel for staff"},
    {"display_name": "84 Lumber", "antera_id": "CUS-LUM-012", "notes": "Pittsburgh-HQ building products — workwear + safety apparel"},
    # National brands
    {"display_name": "Vitamix", "antera_id": "CUS-VTX-020", "notes": "Premium kitchen brand — trade-show merch + retailer incentives"},
    {"display_name": "Fujifilm", "antera_id": "CUS-FUJ-021", "notes": "Tradeshow + corporate gifting"},
    {"display_name": "Siemens", "antera_id": "CUS-SIE-022", "notes": "Industrial — multi-region uniform + safety program"},
    {"display_name": "Skanska", "antera_id": "CUS-SKN-023", "notes": "Construction — site-safety apparel + project commemorative gear"},
    {"display_name": "Big Lots", "antera_id": "CUS-BIG-024", "notes": "Retail — store-team uniforms across 1300+ stores"},
    {"display_name": "Peloton", "antera_id": "CUS-PEL-025", "notes": "Member swag + instructor branded apparel"},
    # Entertainment
    {"display_name": "The Rolling Stones (tour merch)", "antera_id": "CUS-RST-030", "notes": "Tour merch program — high-volume runs, tight deadlines"},
    {"display_name": "Star Wars (Lucasfilm/Disney)", "antera_id": "CUS-SWR-031", "notes": "Licensed character merch — strict brand approval"},
]


# Mocked Antera jobs per customer. Each customer has 2-3 active jobs that a
# field rep / sales rep could file expenses against.
ANTERA_JOBS_TEMPLATE = {
    "Pittsburgh Steelers": [
        ("JOB-STL-2026-0142", "2026 season-opener fan giveaway tees (20K units)"),
        ("JOB-STL-2026-0151", "Training-camp staff polos + caps"),
        ("JOB-STL-2026-0163", "VIP suite gift bags — playoffs"),
    ],
    "Cleveland Cavaliers": [
        ("JOB-CAV-2026-0088", "Court-side staff polos refresh"),
        ("JOB-CAV-2026-0092", "Promo night t-shirts (15K)"),
    ],
    "Arizona Cardinals": [
        ("JOB-ARI-2026-0044", "Season-ticket-holder welcome kits"),
        ("JOB-ARI-2026-0051", "Coaching staff sideline jackets"),
    ],
    "Denver Broncos": [
        ("JOB-DEN-2026-0067", "Cheerleader uniform refresh"),
        ("JOB-DEN-2026-0073", "Stadium concession-team polos"),
    ],
    "New England Patriots": [
        ("JOB-NEP-2026-0029", "Foundation gala embroidered jackets"),
        ("JOB-NEP-2026-0036", "Season giveaway hoodies"),
    ],
    "NFL (league office)": [
        ("JOB-NFL-2026-0200", "Draft event branded merch program"),
        ("JOB-NFL-2026-0211", "International series fan packs"),
    ],
    "Highmark": [
        ("JOB-HMK-2026-0301", "Q2 wellness-box assembly + apparel"),
        ("JOB-HMK-2026-0312", "Annual all-staff polo refresh"),
    ],
    "Allegheny Health Network (AHN)": [
        ("JOB-AHN-2026-0145", "Nurses' week appreciation gear"),
        ("JOB-AHN-2026-0156", "Hospital admin staff embroidered cardigans"),
    ],
    "84 Lumber": [
        ("JOB-LUM-2026-0102", "Store-team hi-vis safety vests"),
        ("JOB-LUM-2026-0118", "Annual conference embroidered polos"),
    ],
    "Vitamix": [
        ("JOB-VTX-2026-0055", "IBIE 2026 trade show booth merch"),
        ("JOB-VTX-2026-0061", "Retailer training-program incentive jackets"),
    ],
    "Fujifilm": [
        ("JOB-FUJ-2026-0033", "NAB 2026 demo-staff polos"),
        ("JOB-FUJ-2026-0040", "Sales kickoff branded hoodies"),
    ],
    "Siemens": [
        ("JOB-SIE-2026-0188", "North America plant safety apparel"),
        ("JOB-SIE-2026-0192", "Engineering team commemorative jackets"),
    ],
    "Skanska": [
        ("JOB-SKN-2026-0077", "Pittsburgh airport project safety vests"),
        ("JOB-SKN-2026-0083", "Project completion crew jackets"),
    ],
    "Big Lots": [
        ("JOB-BIG-2026-0220", "Q3 store-team polo refresh, 1300 locations"),
        ("JOB-BIG-2026-0231", "Distribution-center hi-vis vests"),
    ],
    "Peloton": [
        ("JOB-PEL-2026-0099", "Instructor signature-edition hoodies"),
        ("JOB-PEL-2026-0103", "Member milestone-reward apparel"),
    ],
    "The Rolling Stones (tour merch)": [
        ("JOB-RST-2026-0500", "2026 tour leg-1 venue tees (50K)"),
        ("JOB-RST-2026-0511", "VIP-only embroidered jacket run"),
    ],
    "Star Wars (Lucasfilm/Disney)": [
        ("JOB-SWR-2026-0299", "Star Wars Celebration 2026 cast crew apparel"),
        ("JOB-SWR-2026-0305", "Licensed retail-tier polo program"),
    ],
}


def main():
    print(f"Seeding HDS demo data...")
    existing_names = {c["display_name"] for c in repo.list_customers()}

    created_count = 0
    for cust in HDS_CUSTOMERS:
        if cust["display_name"] in existing_names:
            print(f"  · Skipping existing: {cust['display_name']}")
            continue
        created = repo.create_customer(
            display_name=cust["display_name"],
            antera_customer_id=cust["antera_id"],
            notes=cust["notes"],
        )
        created_count += 1
        print(f"  + Created customer: {cust['display_name']} [{created['customer_id'][:8]}]")

        # Add their mocked Antera jobs
        jobs = ANTERA_JOBS_TEMPLATE.get(cust["display_name"], [])
        for job_id, desc in jobs:
            repo.add_antera_job(created["customer_id"], job_id, desc)

    print(f"\nDone. Created {created_count} new customers.")
    print(f"Total customers in repo: {len(repo.list_customers())}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Analyze oncology trials CSV: trends by year, geography, site type, and sponsor tier."""

import csv
import re
from collections import Counter, defaultdict

INPUT_FILE = "oncology_trials_2022_2025.csv"

# ---------------------------------------------------------------------------
# Large-cap pharma/biotech (~top 25 by market cap / revenue)
# ---------------------------------------------------------------------------
LARGE_CAP = {
    "Johnson & Johnson",
    "Pfizer",
    "Roche",
    "Hoffmann-La Roche",
    "F. Hoffmann-La Roche",
    "Novartis",
    "Merck Sharp & Dohme",
    "Merck & Co",
    "MSD",
    "AbbVie",
    "Eli Lilly",
    "Lilly",
    "AstraZeneca",
    "Bristol-Myers Squibb",
    "Bristol Myers Squibb",
    "Amgen",
    "Gilead Sciences",
    "Gilead",
    "Sanofi",
    "GSK",
    "GlaxoSmithKline",
    "Bayer",
    "Regeneron",
    "Regeneron Pharmaceuticals",
    "Takeda",
    "Novo Nordisk",
    "Boehringer Ingelheim",
    "Astellas",
    "Astellas Pharma",
    "Daiichi Sankyo",
    "Merck KGaA",
    "EMD Serono",
    "Vertex",
    "Vertex Pharmaceuticals",
    "Moderna",
    "BioNTech",
}

# ---------------------------------------------------------------------------
# Mid-market biopharma (established, significant revenue but below large-cap)
# ---------------------------------------------------------------------------
MID_MARKET = {
    "Seagen",
    "Incyte",
    "Incyte Corporation",
    "Jazz Pharmaceuticals",
    "Exact Sciences",
    "BeiGene",
    "Exelixis",
    "Blueprint Medicines",
    "Mirati Therapeutics",
    "Arcus Biosciences",
    "Nektar Therapeutics",
    "Iovance Biotherapeutics",
    "MacroGenics",
    "Immunomedics",
    "Agios Pharmaceuticals",
    "Array BioPharma",
    "Deciphera Pharmaceuticals",
    "Y-mAbs Therapeutics",
    "Relay Therapeutics",
    "Revolution Medicines",
    "Nuvalent",
    "G1 Therapeutics",
    "Turning Point Therapeutics",
    "Zymeworks",
    "iTeos Therapeutics",
    "Zentalis Pharmaceuticals",
    "Merus",
    "CytomX Therapeutics",
    "Syndax Pharmaceuticals",
    "Cullinan Oncology",
    "Ipsen",
    "Eisai",
    "Eisai Co., Ltd.",
    "Servier",
    "Les Laboratoires Servier",
    "Hengrui",
    "Jiangsu HengRui Medicine",
    "Jiangsu Hengrui Pharmaceuticals",
    "Hutchison Medipharma",
    "Zai Lab",
    "Innovent Biologics",
    "Hansoh Pharma",
    "CSPC Pharmaceutical",
    "Kelun",
    "Ono Pharmaceutical",
    "Chugai Pharmaceutical",
    "Sun Pharma",
    "Sun Pharmaceutical",
    "Dr. Reddy's",
    "Teva",
    "Teva Pharmaceutical",
    "Mylan",
    "Viatris",
    "Hikma",
    "Perrigo",
    "Jazz Pharmaceuticals",
    "Alexion",
    "Alexion Pharmaceuticals",
    "Alnyam Pharmaceuticals",
    "BioMarin",
    "BioMarin Pharmaceutical",
    "Horizon Therapeutics",
    "United Therapeutics",
    "Neurocrine Biosciences",
    "Halozyme",
    "Halozyme Therapeutics",
    "Coherus BioSciences",
    "Pierre Fabre",
    "Mundipharma",
    "Otsuka",
    "Otsuka Pharmaceutical",
    "Sumitomo Pharma",
    "Kyowa Kirin",
}

# Patterns for academic/large medical center identification
ACADEMIC_PATTERNS = [
    r"university",
    r"universi(?:ty|tà|té|dad|dade|tät|teit)",
    r"\buniv\b",
    r"medical (?:center|college|school)",
    r"school of medicine",
    r"college of medicine",
    r"teaching hospital",
    r"academic",
    r"(?:mayo|cleveland|johns hopkins|md anderson|memorial sloan|mskcc|dana.farber|"
    r"mass general|cedars.sinai|stanford|duke|emory|vanderbilt|"
    r"mount sinai|nyu langone|ucsf|ucla|upenn|penn medicine|"
    r"columbia university|weill cornell|harvard|yale|"
    r"northwestern memorial|ohio state|michigan medicine|"
    r"ut southwestern|baylor college|fred hutch|city of hope|"
    r"roswell park|moffitt|fox chase|huntsman|"
    r"winship|abramson|siteman|lineberger|"
    r"national cancer institute|national institutes of health|nih clinical center)",
    r"cancer (?:center|institute|hospital)",
    r"research (?:hospital|institute|center)",
    r"children.s hospital",
    r"va medical|veterans affairs",
    r"hospital of the university",
]
ACADEMIC_RE = re.compile("|".join(ACADEMIC_PATTERNS), re.IGNORECASE)


def parse_year(date_str):
    """Extract year from date strings like '2023-05-01' or '2023-05'."""
    if not date_str:
        return None
    m = re.match(r"(\d{4})", date_str)
    return int(m.group(1)) if m else None


def classify_sponsor(name, sponsor_class):
    """Classify sponsor as large_cap, mid_market, or emerging."""
    if sponsor_class != "INDUSTRY":
        return None  # not pharma/biotech
    # Normalize for matching
    name_norm = name.strip()
    for lc in LARGE_CAP:
        if lc.lower() in name_norm.lower() or name_norm.lower() in lc.lower():
            return "large_cap"
    for mm in MID_MARKET:
        if mm.lower() in name_norm.lower() or name_norm.lower() in mm.lower():
            return "mid_market"
    return "emerging"


def is_academic_facility(facility_name):
    return bool(ACADEMIC_RE.search(facility_name))


def main():
    trials = []
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["_year"] = parse_year(row["start_date"])
            row["_has_us"] = row["has_us_site"] == "True"
            row["_countries"] = row["countries"].split("|") if row["countries"] else []
            row["_facilities"] = row["facilities"].split("|") if row["facilities"] else []
            row["_sponsor_tier"] = classify_sponsor(row["lead_sponsor"], row["lead_sponsor_class"])
            trials.append(row)

    years = sorted(set(t["_year"] for t in trials if t["_year"] and 2022 <= t["_year"] <= 2025))

    # ======================================================================
    # Q1: How did the number of trials change over the years?
    # ======================================================================
    print("=" * 70)
    print("Q1: TRIAL VOLUME BY YEAR")
    print("=" * 70)
    year_counts = Counter(t["_year"] for t in trials if t["_year"])
    for y in years:
        c = year_counts[y]
        bar = "█" * (c // 100)
        print(f"  {y}:  {c:>6,}  {bar}")
    print()

    # By phase
    print("  By phase:")
    phase_year = defaultdict(lambda: Counter())
    for t in trials:
        if t["_year"] and 2022 <= t["_year"] <= 2025:
            phase = t["phase"] if t["phase"] else "Not specified"
            phase_year[phase][t["_year"]] += 1

    phase_order = ["EARLY_PHASE1", "PHASE1", "PHASE1|PHASE2", "PHASE2", "PHASE2|PHASE3", "PHASE3", "PHASE4", "NA", "Not specified"]
    print(f"  {'Phase':<20} {'2022':>7} {'2023':>7} {'2024':>7} {'2025':>7}")
    print(f"  {'-'*20} {'-'*7} {'-'*7} {'-'*7} {'-'*7}")
    for phase in phase_order:
        if phase in phase_year:
            vals = [phase_year[phase].get(y, 0) for y in years]
            print(f"  {phase:<20} {vals[0]:>7,} {vals[1]:>7,} {vals[2]:>7,} {vals[3]:>7,}")
    print()

    # ======================================================================
    # Q2: US vs outside US over the years
    # ======================================================================
    print("=" * 70)
    print("Q2: US vs NON-US TRIALS BY YEAR")
    print("=" * 70)
    us_year = Counter()
    nonus_year = Counter()
    both_year = Counter()
    no_location_year = Counter()

    for t in trials:
        y = t["_year"]
        if not y or y not in range(2022, 2026):
            continue
        countries = t["_countries"]
        has_us = t["_has_us"]
        if not countries:
            no_location_year[y] += 1
        elif has_us and len(countries) == 1:
            us_year[y] += 1
        elif has_us and len(countries) > 1:
            both_year[y] += 1
        else:
            nonus_year[y] += 1

    print(f"  {'Category':<25} {'2022':>7} {'2023':>7} {'2024':>7} {'2025':>7}")
    print(f"  {'-'*25} {'-'*7} {'-'*7} {'-'*7} {'-'*7}")
    for label, ctr in [("US only", us_year), ("US + international", both_year), ("Non-US only", nonus_year), ("No location data", no_location_year)]:
        vals = [ctr.get(y, 0) for y in years]
        print(f"  {label:<25} {vals[0]:>7,} {vals[1]:>7,} {vals[2]:>7,} {vals[3]:>7,}")
    print()

    # US involvement total (US only + US+international)
    print("  US involvement (any US site):")
    for y in years:
        us_total = us_year[y] + both_year[y]
        nonus_total = nonus_year[y]
        total_with_loc = us_total + nonus_total
        pct = (us_total / total_with_loc * 100) if total_with_loc else 0
        print(f"    {y}: {us_total:>5,} US ({pct:.1f}%)  |  {nonus_total:>5,} non-US")
    print()

    # Top non-US countries
    print("  Top 15 countries by trial count (all years):")
    country_counts = Counter()
    for t in trials:
        for c in t["_countries"]:
            country_counts[c] += 1
    for country, cnt in country_counts.most_common(15):
        print(f"    {country:<30} {cnt:>6,}")
    print()

    # ======================================================================
    # Q3: US trials - academic vs community sites
    # ======================================================================
    print("=" * 70)
    print("Q3: US TRIALS - ACADEMIC vs COMMUNITY SITES")
    print("=" * 70)

    us_trials = [t for t in trials if t["_has_us"] and t["_year"] and 2022 <= t["_year"] <= 2025]

    acad_year = Counter()
    comm_year = Counter()
    mixed_year = Counter()
    no_facility_year = Counter()

    # For site-level counts
    acad_sites_year = Counter()
    comm_sites_year = Counter()

    for t in us_trials:
        y = t["_year"]
        facilities = t["_facilities"]
        if not facilities:
            no_facility_year[y] += 1
            continue

        acad_count = sum(1 for f in facilities if is_academic_facility(f))
        comm_count = len(facilities) - acad_count

        acad_sites_year[y] += acad_count
        comm_sites_year[y] += comm_count

        if acad_count > 0 and comm_count == 0:
            acad_year[y] += 1
        elif acad_count == 0 and comm_count > 0:
            comm_year[y] += 1
        else:
            mixed_year[y] += 1

    print(f"\n  Trial classification (by whether sites are academic, community, or mixed):")
    print(f"  {'Category':<30} {'2022':>7} {'2023':>7} {'2024':>7} {'2025':>7}")
    print(f"  {'-'*30} {'-'*7} {'-'*7} {'-'*7} {'-'*7}")
    for label, ctr in [
        ("Academic sites only", acad_year),
        ("Community sites only", comm_year),
        ("Mixed (academic + community)", mixed_year),
        ("No facility data", no_facility_year),
    ]:
        vals = [ctr.get(y, 0) for y in years]
        print(f"  {label:<30} {vals[0]:>7,} {vals[1]:>7,} {vals[2]:>7,} {vals[3]:>7,}")

    print(f"\n  Site-level counts (individual US sites across all trials):")
    print(f"  {'Site type':<20} {'2022':>7} {'2023':>7} {'2024':>7} {'2025':>7}")
    print(f"  {'-'*20} {'-'*7} {'-'*7} {'-'*7} {'-'*7}")
    for label, ctr in [("Academic", acad_sites_year), ("Community", comm_sites_year)]:
        vals = [ctr.get(y, 0) for y in years]
        print(f"  {label:<20} {vals[0]:>7,} {vals[1]:>7,} {vals[2]:>7,} {vals[3]:>7,}")

    for y in years:
        total_sites = acad_sites_year[y] + comm_sites_year[y]
        if total_sites:
            pct = acad_sites_year[y] / total_sites * 100
            print(f"    {y}: Academic share = {pct:.1f}%")
    print()

    # ======================================================================
    # Q4: Industry trials by sponsor tier
    # ======================================================================
    print("=" * 70)
    print("Q4: INDUSTRY ONCOLOGY TRIALS BY SPONSOR TIER")
    print("=" * 70)

    industry_trials = [t for t in trials if t["_sponsor_tier"] is not None]
    non_industry = len(trials) - len(industry_trials)

    tier_year = defaultdict(Counter)
    for t in industry_trials:
        y = t["_year"]
        if y and 2022 <= y <= 2025:
            tier_year[t["_sponsor_tier"]][y] += 1

    print(f"\n  Overall: {len(industry_trials):,} industry-sponsored  |  {non_industry:,} non-industry (academic/govt/other)")
    print()
    print(f"  {'Sponsor tier':<20} {'2022':>7} {'2023':>7} {'2024':>7} {'2025':>7}  {'Total':>7}")
    print(f"  {'-'*20} {'-'*7} {'-'*7} {'-'*7} {'-'*7}  {'-'*7}")
    for tier in ["large_cap", "mid_market", "emerging"]:
        vals = [tier_year[tier].get(y, 0) for y in years]
        total = sum(vals)
        label = tier.replace("_", " ").title()
        print(f"  {label:<20} {vals[0]:>7,} {vals[1]:>7,} {vals[2]:>7,} {vals[3]:>7,}  {total:>7,}")
    print()

    # Share of industry trials
    print("  Share of industry trials by tier:")
    for y in years:
        total_ind = sum(tier_year[tier][y] for tier in tier_year)
        if total_ind:
            parts = []
            for tier in ["large_cap", "mid_market", "emerging"]:
                pct = tier_year[tier][y] / total_ind * 100
                parts.append(f"{tier.replace('_',' ').title()}: {pct:.1f}%")
            print(f"    {y}: {' | '.join(parts)}")
    print()

    # Top sponsors in each tier
    for tier in ["large_cap", "mid_market", "emerging"]:
        sponsor_counts = Counter()
        for t in industry_trials:
            if t["_sponsor_tier"] == tier:
                sponsor_counts[t["lead_sponsor"]] += 1
        label = tier.replace("_", " ").title()
        print(f"  Top {label} sponsors:")
        for name, cnt in sponsor_counts.most_common(10):
            print(f"    {name:<50} {cnt:>5,}")
        print()


if __name__ == "__main__":
    main()

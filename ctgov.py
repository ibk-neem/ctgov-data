#!/usr/bin/env python3
"""CLI tool for querying the ClinicalTrials.gov API v2."""

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request

BASE_URL = "https://clinicaltrials.gov/api/v2"

VALID_STATUSES = [
    "RECRUITING",
    "NOT_YET_RECRUITING",
    "ENROLLING_BY_INVITATION",
    "ACTIVE_NOT_RECRUITING",
    "SUSPENDED",
    "TERMINATED",
    "COMPLETED",
    "WITHDRAWN",
]

VALID_PHASES = ["EARLY_PHASE1", "PHASE1", "PHASE2", "PHASE3", "PHASE4", "NA"]

VALID_SORT_FIELDS = [
    "LastUpdatePostDate",
    "EnrollmentCount",
    "StartDate",
    "StudyFirstPostDate",
]


def api_request(endpoint, params=None):
    """Make a GET request to the ClinicalTrials.gov API."""
    url = f"{BASE_URL}{endpoint}"
    if params:
        params = {k: v for k, v in params.items() if v is not None}
        url += "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(url)
    req.add_header("Accept", "application/json")

    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.readable() else ""
        print(f"HTTP {e.code}: {e.reason}", file=sys.stderr)
        if body:
            print(body, file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Connection error: {e.reason}", file=sys.stderr)
        sys.exit(1)


def format_study_summary(study):
    """Format a study for display in search results."""
    proto = study.get("protocolSection", {})
    ident = proto.get("identificationModule", {})
    status_mod = proto.get("statusModule", {})
    design = proto.get("designModule", {})
    desc = proto.get("descriptionModule", {})
    conditions = proto.get("conditionsModule", {})
    sponsors = proto.get("sponsorCollaboratorsModule", {})
    eligibility = proto.get("eligibilityModule", {})

    nct_id = ident.get("nctId", "N/A")
    title = ident.get("briefTitle", "N/A")
    status = status_mod.get("overallStatus", "N/A")
    phase = (design.get("phases") or ["N/A"])[0] if design.get("phases") else "N/A"
    enrollment = design.get("enrollmentInfo", {}).get("count", "N/A")
    start_date = status_mod.get("startDateStruct", {}).get("date", "N/A")
    completion_date = status_mod.get("completionDateStruct", {}).get("date", "N/A")
    lead_sponsor = sponsors.get("leadSponsor", {}).get("name", "N/A")
    condition_list = conditions.get("conditions", [])
    brief_summary = desc.get("briefSummary", "")
    sex = eligibility.get("sex", "N/A")
    min_age = eligibility.get("minimumAge", "N/A")
    max_age = eligibility.get("maximumAge", "N/A")

    lines = [
        f"  {nct_id}  {title}",
        f"  Status: {status}  |  Phase: {phase}  |  Enrollment: {enrollment}",
        f"  Sponsor: {lead_sponsor}",
        f"  Dates: {start_date} → {completion_date}",
    ]
    if condition_list:
        lines.append(f"  Conditions: {', '.join(condition_list[:5])}")
    if sex != "ALL" or min_age != "N/A" or max_age != "N/A":
        lines.append(f"  Eligibility: {sex}, {min_age} - {max_age}")
    if brief_summary:
        summary = brief_summary[:200].replace("\n", " ")
        if len(brief_summary) > 200:
            summary += "..."
        lines.append(f"  Summary: {summary}")

    return "\n".join(lines)


def cmd_search(args):
    """Search for clinical trials."""
    params = {
        "format": "json",
        "pageSize": args.page_size,
    }

    if args.condition:
        params["query.cond"] = args.condition
    if args.intervention:
        params["query.intr"] = args.intervention
    if args.term:
        params["query.term"] = args.term
    if args.sponsor:
        params["query.spons"] = args.sponsor
    if args.location:
        params["query.locn"] = args.location
    if args.status:
        statuses = [s.strip().upper() for s in args.status.split(",")]
        for s in statuses:
            if s not in VALID_STATUSES:
                print(f"Invalid status: {s}", file=sys.stderr)
                print(f"Valid statuses: {', '.join(VALID_STATUSES)}", file=sys.stderr)
                sys.exit(1)
        params["filter.overallStatus"] = ",".join(statuses)
    if args.phase:
        phases = [p.strip().upper() for p in args.phase.split(",")]
        for p in phases:
            if p not in VALID_PHASES:
                print(f"Invalid phase: {p}", file=sys.stderr)
                print(f"Valid phases: {', '.join(VALID_PHASES)}", file=sys.stderr)
                sys.exit(1)
        params["filter.phase"] = ",".join(phases)
    if args.sort:
        params["sort"] = args.sort

    if args.json:
        all_studies = []
        page_token = None
        pages_fetched = 0
        while True:
            if page_token:
                params["pageToken"] = page_token
            data = api_request("/studies", params)
            all_studies.extend(data.get("studies", []))
            pages_fetched += 1
            page_token = data.get("nextPageToken")
            if not page_token or (args.max_pages and pages_fetched >= args.max_pages):
                break
            time.sleep(1.2)  # respect rate limit
        print(json.dumps(all_studies, indent=2))
        return

    page_token = None
    total_shown = 0
    pages_fetched = 0

    while True:
        if page_token:
            params["pageToken"] = page_token
        data = api_request("/studies", params)
        studies = data.get("studies", [])
        total = data.get("totalCount", 0)

        if pages_fetched == 0:
            print(f"Found {total} studies\n")

        for study in studies:
            total_shown += 1
            print(f"[{total_shown}]")
            print(format_study_summary(study))
            print()

        pages_fetched += 1
        page_token = data.get("nextPageToken")

        if not page_token:
            break
        if args.max_pages and pages_fetched >= args.max_pages:
            remaining = total - total_shown
            if remaining > 0:
                print(f"... {remaining} more studies (use --max-pages to see more)")
            break

        time.sleep(1.2)  # respect rate limit

    if total_shown == 0:
        print("No studies found.")


def cmd_study(args):
    """Get details for a specific study by NCT ID."""
    nct_id = args.nct_id.upper()
    if not nct_id.startswith("NCT"):
        nct_id = "NCT" + nct_id

    data = api_request(f"/studies/{nct_id}", {"format": "json"})

    if args.json:
        print(json.dumps(data, indent=2))
        return

    proto = data.get("protocolSection", {})
    ident = proto.get("identificationModule", {})
    status_mod = proto.get("statusModule", {})
    desc = proto.get("descriptionModule", {})
    design = proto.get("designModule", {})
    conditions = proto.get("conditionsModule", {})
    sponsors = proto.get("sponsorCollaboratorsModule", {})
    eligibility = proto.get("eligibilityModule", {})
    arms = proto.get("armsInterventionsModule", {})
    outcomes = proto.get("outcomesModule", {})
    contacts = proto.get("contactsLocationsModule", {})

    print(f"{'=' * 70}")
    print(f"  {ident.get('nctId', 'N/A')}  {ident.get('briefTitle', 'N/A')}")
    print(f"{'=' * 70}")

    org = ident.get("organization", {})
    if org:
        print(f"\nOrganization: {org.get('fullName', 'N/A')}")
    print(f"Official Title: {ident.get('officialTitle', 'N/A')}")

    print(f"\n--- Status ---")
    print(f"Overall Status: {status_mod.get('overallStatus', 'N/A')}")
    print(f"Start Date: {status_mod.get('startDateStruct', {}).get('date', 'N/A')}")
    print(f"Completion Date: {status_mod.get('completionDateStruct', {}).get('date', 'N/A')}")

    print(f"\n--- Design ---")
    phases = design.get("phases", [])
    print(f"Phase: {', '.join(phases) if phases else 'N/A'}")
    print(f"Study Type: {design.get('studyType', 'N/A')}")
    enrollment_info = design.get("enrollmentInfo", {})
    print(f"Enrollment: {enrollment_info.get('count', 'N/A')} ({enrollment_info.get('type', '')})")

    conds = conditions.get("conditions", [])
    if conds:
        print(f"\n--- Conditions ---")
        for c in conds:
            print(f"  - {c}")

    keywords = conditions.get("keywords", [])
    if keywords:
        print(f"\n--- Keywords ---")
        print(f"  {', '.join(keywords)}")

    lead = sponsors.get("leadSponsor", {})
    collabs = sponsors.get("collaborators", [])
    print(f"\n--- Sponsors ---")
    print(f"Lead: {lead.get('name', 'N/A')} ({lead.get('class', '')})")
    for c in collabs:
        print(f"Collaborator: {c.get('name', 'N/A')} ({c.get('class', '')})")

    if desc.get("briefSummary"):
        print(f"\n--- Brief Summary ---")
        print(desc["briefSummary"])

    if desc.get("detailedDescription"):
        print(f"\n--- Detailed Description ---")
        print(desc["detailedDescription"])

    print(f"\n--- Eligibility ---")
    print(f"Sex: {eligibility.get('sex', 'N/A')}")
    print(f"Min Age: {eligibility.get('minimumAge', 'N/A')}")
    print(f"Max Age: {eligibility.get('maximumAge', 'N/A')}")
    print(f"Healthy Volunteers: {eligibility.get('healthyVolunteers', 'N/A')}")
    criteria = eligibility.get("eligibilityCriteria", "")
    if criteria:
        print(f"\nCriteria:\n{criteria}")

    arm_list = arms.get("armGroups", [])
    if arm_list:
        print(f"\n--- Arms ---")
        for arm in arm_list:
            label = arm.get("label", "N/A")
            arm_type = arm.get("type", "")
            arm_desc = arm.get("description", "")
            print(f"  [{arm_type}] {label}")
            if arm_desc:
                print(f"    {arm_desc}")

    interventions = arms.get("interventions", [])
    if interventions:
        print(f"\n--- Interventions ---")
        for intv in interventions:
            print(f"  [{intv.get('type', '')}] {intv.get('name', 'N/A')}")
            if intv.get("description"):
                print(f"    {intv['description']}")

    primary = outcomes.get("primaryOutcomes", [])
    secondary = outcomes.get("secondaryOutcomes", [])
    if primary:
        print(f"\n--- Primary Outcomes ---")
        for o in primary:
            print(f"  - {o.get('measure', 'N/A')}")
            if o.get("timeFrame"):
                print(f"    Time frame: {o['timeFrame']}")
    if secondary:
        print(f"\n--- Secondary Outcomes ---")
        for o in secondary:
            print(f"  - {o.get('measure', 'N/A')}")
            if o.get("timeFrame"):
                print(f"    Time frame: {o['timeFrame']}")

    locations = contacts.get("locations", [])
    if locations:
        print(f"\n--- Locations ({len(locations)}) ---")
        for loc in locations[:10]:
            facility = loc.get("facility", "N/A")
            city = loc.get("city", "")
            state = loc.get("state", "")
            country = loc.get("country", "")
            loc_status = loc.get("status", "")
            parts = [p for p in [city, state, country] if p]
            print(f"  - {facility}, {', '.join(parts)}  [{loc_status}]")
        if len(locations) > 10:
            print(f"  ... and {len(locations) - 10} more locations")

    results = data.get("resultsSection")
    if results:
        print(f"\n--- Results Available ---")
        adverse = results.get("adverseEventsModule")
        if adverse:
            print(f"  Adverse events data: Yes")
        outcome_measures = results.get("outcomeMeasuresModule", {}).get("outcomeMeasures", [])
        if outcome_measures:
            print(f"  Outcome measures: {len(outcome_measures)}")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="Query the ClinicalTrials.gov API v2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""examples:
  %(prog)s search --condition "lung cancer" --status RECRUITING
  %(prog)s search --intervention "Pembrolizumab" --phase PHASE3
  %(prog)s search --term "diabetes" --location "New York" --page-size 5
  %(prog)s search --sponsor "Pfizer" --sort "EnrollmentCount:desc"
  %(prog)s study NCT04267848
  %(prog)s study NCT04267848 --json""",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # search subcommand
    search_parser = subparsers.add_parser("search", help="Search for clinical trials")
    search_parser.add_argument("-c", "--condition", help="Disease or condition")
    search_parser.add_argument("-i", "--intervention", help="Treatment or intervention")
    search_parser.add_argument("-t", "--term", help="Full-text search term")
    search_parser.add_argument("-s", "--sponsor", help="Sponsor or collaborator")
    search_parser.add_argument("-l", "--location", help="Geographic location")
    search_parser.add_argument(
        "--status",
        help=f"Comma-separated statuses: {', '.join(VALID_STATUSES)}",
    )
    search_parser.add_argument(
        "--phase",
        help=f"Comma-separated phases: {', '.join(VALID_PHASES)}",
    )
    search_parser.add_argument(
        "--sort",
        help="Sort field:direction (e.g. EnrollmentCount:desc)",
    )
    search_parser.add_argument(
        "--page-size", type=int, default=10, help="Results per page (default: 10, max: 1000)"
    )
    search_parser.add_argument(
        "--max-pages", type=int, default=1, help="Max pages to fetch (default: 1)"
    )
    search_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    # study subcommand
    study_parser = subparsers.add_parser("study", help="Get details for a specific study")
    study_parser.add_argument("nct_id", help="NCT ID of the study (e.g. NCT04267848)")
    study_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    args = parser.parse_args()

    if args.command == "search":
        cmd_search(args)
    elif args.command == "study":
        cmd_study(args)


if __name__ == "__main__":
    main()

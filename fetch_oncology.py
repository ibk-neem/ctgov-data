#!/usr/bin/env python3
"""Fetch all oncology/cancer trials from 2022-2025 and export to CSV."""

import csv
import json
import sys
import time
import urllib.parse
import urllib.request

BASE_URL = "https://clinicaltrials.gov/api/v2"
OUTPUT_FILE = "oncology_trials_2022_2025.csv"

CSV_COLUMNS = [
    "nct_id",
    "brief_title",
    "official_title",
    "overall_status",
    "phase",
    "study_type",
    "enrollment",
    "enrollment_type",
    "start_date",
    "completion_date",
    "last_update_post_date",
    "lead_sponsor",
    "lead_sponsor_class",
    "collaborators",
    "conditions",
    "keywords",
    "interventions",
    "primary_outcomes",
    "secondary_outcomes",
    "sex",
    "min_age",
    "max_age",
    "healthy_volunteers",
    "study_url",
]


def api_request(endpoint, params):
    url = f"{BASE_URL}{endpoint}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def extract_row(study):
    proto = study.get("protocolSection", {})
    ident = proto.get("identificationModule", {})
    status_mod = proto.get("statusModule", {})
    design = proto.get("designModule", {})
    desc = proto.get("descriptionModule", {})
    conditions = proto.get("conditionsModule", {})
    sponsors = proto.get("sponsorCollaboratorsModule", {})
    eligibility = proto.get("eligibilityModule", {})
    arms = proto.get("armsInterventionsModule", {})
    outcomes = proto.get("outcomesModule", {})

    nct_id = ident.get("nctId", "")
    phases = design.get("phases", [])
    enrollment_info = design.get("enrollmentInfo", {})
    lead = sponsors.get("leadSponsor", {})
    collabs = sponsors.get("collaborators", [])
    interventions = arms.get("interventions", [])
    primary = outcomes.get("primaryOutcomes", [])
    secondary = outcomes.get("secondaryOutcomes", [])

    return {
        "nct_id": nct_id,
        "brief_title": ident.get("briefTitle", ""),
        "official_title": ident.get("officialTitle", ""),
        "overall_status": status_mod.get("overallStatus", ""),
        "phase": "|".join(phases) if phases else "",
        "study_type": design.get("studyType", ""),
        "enrollment": enrollment_info.get("count", ""),
        "enrollment_type": enrollment_info.get("type", ""),
        "start_date": status_mod.get("startDateStruct", {}).get("date", ""),
        "completion_date": status_mod.get("completionDateStruct", {}).get("date", ""),
        "last_update_post_date": status_mod.get("lastUpdatePostDateStruct", {}).get("date", ""),
        "lead_sponsor": lead.get("name", ""),
        "lead_sponsor_class": lead.get("class", ""),
        "collaborators": "|".join(c.get("name", "") for c in collabs),
        "conditions": "|".join(conditions.get("conditions", [])),
        "keywords": "|".join(conditions.get("keywords", [])),
        "interventions": "|".join(
            f"{i.get('type', '')}:{i.get('name', '')}" for i in interventions
        ),
        "primary_outcomes": "|".join(o.get("measure", "") for o in primary),
        "secondary_outcomes": "|".join(o.get("measure", "") for o in secondary),
        "sex": eligibility.get("sex", ""),
        "min_age": eligibility.get("minimumAge", ""),
        "max_age": eligibility.get("maximumAge", ""),
        "healthy_volunteers": eligibility.get("healthyVolunteers", ""),
        "study_url": f"https://clinicaltrials.gov/study/{nct_id}" if nct_id else "",
    }


def main():
    params = {
        "format": "json",
        "pageSize": 1000,
        "countTotal": "true",
        "query.cond": "cancer OR oncology",
        "filter.advanced": "AREA[StartDate]RANGE[2022-01-01, 2025-12-31]",
    }

    # First request to get total count
    data = api_request("/studies", params)
    total = data.get("totalCount", 0)
    print(f"Total trials to fetch: {total}")

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()

        page = 1
        fetched = 0

        while True:
            studies = data.get("studies", [])
            for study in studies:
                writer.writerow(extract_row(study))
                fetched += 1

            print(f"  Page {page}: wrote {len(studies)} studies ({fetched}/{total})")

            page_token = data.get("nextPageToken")
            if not page_token:
                break

            page += 1
            params["pageToken"] = page_token
            # Remove countTotal after first request to speed up
            params.pop("countTotal", None)

            time.sleep(1.2)  # respect ~50 req/min rate limit

            try:
                data = api_request("/studies", params)
            except Exception as e:
                print(f"  Error on page {page}: {e}", file=sys.stderr)
                print("  Retrying in 10 seconds...", file=sys.stderr)
                time.sleep(10)
                try:
                    data = api_request("/studies", params)
                except Exception as e2:
                    print(f"  Failed again: {e2}. Stopping.", file=sys.stderr)
                    break

    print(f"\nDone. {fetched} trials written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()

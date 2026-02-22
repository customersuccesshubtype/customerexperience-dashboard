"""
Fetches Jira tickets from the Delivery (PS) project and appends a daily snapshot
to data/snapshots.json and updates data/tickets.json with the full current list.
"""

import json
import os
import requests
from datetime import datetime, timezone
from pathlib import Path

# --- Config from environment ---
BASE_URL = os.environ["JIRA_BASE_URL"].rstrip("/")
EMAIL = os.environ["JIRA_EMAIL"]
TOKEN = os.environ["JIRA_API_TOKEN"]
PROJECT_KEY = os.environ.get("JIRA_PROJECT_KEY", "PS")

AUTH = (EMAIL, TOKEN)
HEADERS = {"Accept": "application/json"}

# Status categories
DONE_STATUSES = {"Done", "Closed"}
OPEN_STATUSES = {"To Do", "Open", "In Progress", "Ready for review", "Ready to Deliver"}

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)


def fetch_all_issues():
    """Fetch all issues from the project using pagination."""
    issues = []
    next_page_token = None
    max_results = 100

    while True:
        url = f"{BASE_URL}/rest/api/3/search/jql"
        body = {
            "jql": f"project = {PROJECT_KEY} ORDER BY created DESC",
            "maxResults": max_results,
            "fields": ["summary", "status", "assignee", "issuetype", "created", "resolutiondate", "labels"],
        }
        if next_page_token:
            body["nextPageToken"] = next_page_token

        resp = requests.post(url, json=body, auth=AUTH, headers={**HEADERS, "Content-Type": "application/json"})
        resp.raise_for_status()
        data = resp.json()

        batch = data.get("issues", [])
        issues.extend(batch)
        print(f"  Fetched {len(issues)} issues so far...")

        next_page_token = data.get("nextPageToken")
        if not next_page_token or not batch:
            break

    return issues


def parse_issue(issue):
    fields = issue["fields"]
    assignee = fields.get("assignee")
    return {
        "key": issue["key"],
        "summary": fields.get("summary", ""),
        "status": fields["status"]["name"],
        "status_category": fields["status"]["statusCategory"]["name"],
        "assignee": assignee["displayName"] if assignee else None,
        "issuetype": fields["issuetype"]["name"],
        "created": fields.get("created", "")[:10],  # date only
        "resolutiondate": (fields.get("resolutiondate") or "")[:10],
        "labels": fields.get("labels", []),
    }


def compute_snapshot(tickets):
    """Compute counts per status and per assignee for a given list of tickets."""
    by_status = {}
    by_assignee = {}

    for t in tickets:
        status = t["status"]
        by_status[status] = by_status.get(status, 0) + 1

        person = t["assignee"] or "Unassigned"
        if person not in by_assignee:
            by_assignee[person] = {"open": 0, "done": 0, "in_progress": 0}

        if status in DONE_STATUSES:
            by_assignee[person]["done"] += 1
        elif status == "In Progress":
            by_assignee[person]["in_progress"] += 1
        else:
            by_assignee[person]["open"] += 1

    total_done = sum(by_status.get(s, 0) for s in DONE_STATUSES)
    total_open = sum(by_status.get(s, 0) for s in OPEN_STATUSES)

    return {
        "total_open": total_open,
        "total_done": total_done,
        "total": total_open + total_done,
        "by_status": by_status,
        "by_assignee": by_assignee,
    }


def load_json(path, default):
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def main():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"Fetching Jira issues for project {PROJECT_KEY}...")

    raw_issues = fetch_all_issues()
    tickets = [parse_issue(i) for i in raw_issues]
    print(f"Total tickets: {len(tickets)}")

    # Save full ticket list
    save_json(DATA_DIR / "tickets.json", {
        "last_updated": today,
        "tickets": tickets,
    })

    # Append daily snapshot
    snapshot = compute_snapshot(tickets)
    snapshot["date"] = today

    snapshots_path = DATA_DIR / "snapshots.json"
    snapshots = load_json(snapshots_path, [])

    # Replace today's snapshot if it already exists
    snapshots = [s for s in snapshots if s["date"] != today]
    snapshots.append(snapshot)
    snapshots.sort(key=lambda s: s["date"])

    save_json(snapshots_path, snapshots)
    print(f"Snapshot saved: {snapshot['total_open']} open, {snapshot['total_done']} done")


if __name__ == "__main__":
    main()

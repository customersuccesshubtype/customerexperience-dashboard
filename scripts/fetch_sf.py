"""
Fetches Salesforce Cases and saves a daily snapshot to data/sf_cases.json.
Authentication: Username + Password + Security Token (Resource Owner Password flow).

Required environment variables (set as GitHub Secrets):
  SF_INSTANCE_URL        e.g. https://hubtype.my.salesforce.com
  SF_CLIENT_ID           Connected App Consumer Key
  SF_CLIENT_SECRET       Connected App Consumer Secret
  SF_USERNAME            Salesforce username (email)
  SF_PASSWORD_WITH_TOKEN Password concatenated with Security Token (no space)
"""

import json
import os
import requests
from datetime import datetime, timezone
from pathlib import Path

INSTANCE_URL   = os.environ["SF_INSTANCE_URL"].rstrip("/")
CLIENT_ID      = os.environ["SF_CLIENT_ID"]
CLIENT_SECRET  = os.environ["SF_CLIENT_SECRET"]
USERNAME       = os.environ["SF_USERNAME"]
PASSWORD_TOKEN = os.environ["SF_PASSWORD_WITH_TOKEN"]

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)


def authenticate():
    resp = requests.post(f"{INSTANCE_URL}/services/oauth2/token", data={
        "grant_type":    "password",
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "username":      USERNAME,
        "password":      PASSWORD_TOKEN,
    })
    resp.raise_for_status()
    token_data = resp.json()
    print(f"  Authenticated as: {USERNAME}")
    return token_data["access_token"], token_data["instance_url"]


def query(access_token, instance_url, soql):
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    records = []
    url = f"{instance_url}/services/data/v59.0/query"
    params = {"q": soql}
    while True:
        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
        records.extend(data.get("records", []))
        print(f"  Fetched {len(records)} / {data.get('totalSize', '?')} cases...")
        next_url = data.get("nextRecordsUrl")
        if not next_url:
            break
        url = f"{instance_url}{next_url}"
        params = {}
    return records


def parse_case(rec):
    def date_only(val):
        return (val or "")[:10]

    owner = rec.get("Owner") or {}
    account = rec.get("Account") or {}

    return {
        "id":              rec.get("Id"),
        "case_number":     rec.get("CaseNumber"),
        "subject":         rec.get("Subject") or "",
        "status":          rec.get("Status") or "",
        "priority":        rec.get("Priority") or "",
        "is_closed":       rec.get("IsClosed", False),
        "is_escalated":    rec.get("IsEscalated", False),
        "owner":           owner.get("Name") or rec.get("OwnerId") or "",
        "account":         account.get("Name") or "",
        "origin":          rec.get("Origin") or "",
        "type":            rec.get("Type") or "",
        "feeling":         rec.get("Feeling__c") or "",
        "issue_type":      rec.get("Issue_Type__c") or "",
        "channel":         rec.get("Channel__c") or "",
        "is_critical":     rec.get("Is_critical__c") or "",
        "escalated_team":  rec.get("Escalated_Team__c") or "",
        "resolution_time": rec.get("Resolution_time__c") or "",
        "created":         date_only(rec.get("CreatedDate")),
        "closed":          date_only(rec.get("ClosedDate")),
        "last_modified":   date_only(rec.get("LastModifiedDate")),
    }


SOQL = """
SELECT
  Id, CaseNumber, Subject, Status, Priority, IsClosed, IsEscalated,
  Owner.Name, Account.Name, Origin, Type,
  Feeling__c, Issue_Type__c, Channel__c, Is_critical__c,
  Escalated_Team__c, Resolution_time__c,
  CreatedDate, ClosedDate, LastModifiedDate
FROM Case
ORDER BY CreatedDate DESC
""".strip()


def main():
    now = datetime.now(timezone.utc)
    last_updated = now.strftime("%Y-%m-%d %H:%M UTC")

    print("Authenticating with Salesforce...")
    access_token, instance_url = authenticate()

    print("Fetching Cases...")
    raw_records = query(access_token, instance_url, SOQL)
    cases = [parse_case(r) for r in raw_records]
    print(f"Total cases parsed: {len(cases)}")

    output = {
        "last_updated": last_updated,
        "cases": cases,
    }

    out_path = DATA_DIR / "sf_cases.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(cases)} cases to {out_path}")


if __name__ == "__main__":
    main()

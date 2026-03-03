"""
Fetches Salesforce Cases and Opportunities, saves daily snapshots to data/.
Authentication: OAuth 2.0 Client Credentials flow (no username/password needed).

Required environment variables (set as GitHub Secrets):
  SF_INSTANCE_URL   e.g. https://hubtype.my.salesforce.com
  SF_CLIENT_ID      External Client App Consumer Key
  SF_CLIENT_SECRET  External Client App Consumer Secret
"""

import json
import os
import requests
from datetime import datetime, timezone
from pathlib import Path

INSTANCE_URL  = os.environ["SF_INSTANCE_URL"].rstrip("/")
CLIENT_ID     = os.environ["SF_CLIENT_ID"]
CLIENT_SECRET = os.environ["SF_CLIENT_SECRET"]

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)


def authenticate():
    resp = requests.post(f"{INSTANCE_URL}/services/oauth2/token", data={
        "grant_type":    "client_credentials",
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    })
    resp.raise_for_status()
    token_data = resp.json()
    print(f"  Authenticated via Client Credentials flow")
    return token_data["access_token"], token_data["instance_url"]


def query(access_token, instance_url, soql, label="records"):
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    records = []
    url = f"{instance_url}/services/data/v59.0/query"
    params = {"q": soql}
    while True:
        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
        records.extend(data.get("records", []))
        print(f"  Fetched {len(records)} / {data.get('totalSize', '?')} {label}...")
        next_url = data.get("nextRecordsUrl")
        if not next_url:
            break
        url = f"{instance_url}{next_url}"
        params = {}
    return records


# ---- Cases ----------------------------------------------------------------

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


CASES_SOQL = """
SELECT
  Id, CaseNumber, Subject, Status, Priority, IsClosed, IsEscalated,
  Owner.Name, Account.Name, Origin, Type,
  Feeling__c, Issue_Type__c, Channel__c, Is_critical__c,
  Escalated_Team__c, Resolution_time__c,
  CreatedDate, ClosedDate, LastModifiedDate
FROM Case
ORDER BY CreatedDate DESC
""".strip()


# ---- Opportunities --------------------------------------------------------

def parse_opportunity(rec):
    def date_only(val):
        return (val or "")[:10]

    owner   = rec.get("Owner")   or {}
    account = rec.get("Account") or {}

    opp_type = rec.get("Type") or ""
    arr_amount = rec.get("ARR_Amount__c")  # None for Consultancy
    amount     = rec.get("Amount")

    return {
        "id":          rec.get("Id"),
        "name":        rec.get("Name") or "",
        "type":        opp_type,
        "stage":       rec.get("StageName") or "",
        "is_closed":   rec.get("IsClosed", False),
        "is_won":      rec.get("IsWon", False),
        "probability": rec.get("Probability"),
        "amount":      amount,
        "arr":         arr_amount,   # null for Consultancy
        "owner":       owner.get("Name") or "",
        "account":     account.get("Name") or "",
        "created":     date_only(rec.get("CreatedDate")),
        "close_date":  date_only(rec.get("CloseDate")),
        "start_date":  date_only(rec.get("Start_date__c")),
    }


OPPORTUNITIES_SOQL = """
SELECT
  Id, Name, Type, StageName, IsClosed, IsWon, Probability,
  Amount, ARR_Amount__c,
  Owner.Name, Account.Name,
  CreatedDate, CloseDate, Start_date__c
FROM Opportunity
WHERE Type IN ('Consultancy', 'Renewal', 'Upsell')
ORDER BY CreatedDate DESC
""".strip()


# ---- Main ----------------------------------------------------------------

def main():
    now = datetime.now(timezone.utc)
    last_updated = now.strftime("%Y-%m-%d %H:%M UTC")

    print("Authenticating with Salesforce...")
    access_token, instance_url = authenticate()

    print("Fetching Cases...")
    raw_cases = query(access_token, instance_url, CASES_SOQL, label="cases")
    cases = [parse_case(r) for r in raw_cases]
    print(f"Total cases parsed: {len(cases)}")

    out_cases = DATA_DIR / "sf_cases.json"
    with open(out_cases, "w") as f:
        json.dump({"last_updated": last_updated, "cases": cases}, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(cases)} cases to {out_cases}")

    print("Fetching Opportunities...")
    raw_opps = query(access_token, instance_url, OPPORTUNITIES_SOQL, label="opportunities")
    opps = [parse_opportunity(r) for r in raw_opps]
    print(f"Total opportunities parsed: {len(opps)}")

    out_opps = DATA_DIR / "sf_opportunities.json"
    with open(out_opps, "w") as f:
        json.dump({"last_updated": last_updated, "opportunities": opps}, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(opps)} opportunities to {out_opps}")


if __name__ == "__main__":
    main()

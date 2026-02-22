# Delivery Dashboard

A static GitHub Pages dashboard that tracks Jira tickets from the Delivery project. Updated daily via GitHub Actions.

## How it works

1. A GitHub Action runs every day at 07:00 UTC
2. It fetches all tickets from the Jira `PS` project using the REST API
3. It saves the data to `data/tickets.json` and appends a snapshot to `data/snapshots.json`
4. GitHub Pages serves `index.html` which reads those files and renders charts

## Setup

### 1. Create the repo

Create a new repo in the `customersuccesshubtype` GitHub org (e.g. `delivery-dashboard`).

### 2. Add GitHub Secrets

Go to **Settings > Secrets and variables > Actions** and add:

| Secret | Value |
|--------|-------|
| `JIRA_BASE_URL` | `https://hubtype.atlassian.net` |
| `JIRA_EMAIL` | Your Atlassian account email |
| `JIRA_API_TOKEN` | Your Jira API token (see below) |
| `JIRA_PROJECT_KEY` | `PS` |

**How to get a Jira API token:**
1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
2. Click "Create API token"
3. Copy the value and paste it as the `JIRA_API_TOKEN` secret

### 3. Enable GitHub Pages

Go to **Settings > Pages** and set:
- Source: `Deploy from a branch`
- Branch: `main`, folder: `/ (root)`

### 4. Run the action manually (first time)

Go to **Actions > Fetch Jira Data > Run workflow** to generate the data files immediately.
After that it runs automatically every day at 07:00 UTC.

### 5. Access the dashboard

Your dashboard will be at:
`https://customersuccesshubtype.github.io/delivery-dashboard/`

## Features

- KPI counters: total, open, in-progress, done
- Trend chart: open vs done over time (weekly or monthly)
- Status breakdown: doughnut chart
- Work by person: stacked bar chart
- Filterable ticket list with links to Jira
- Filters: by person, period (30d / 90d / 6m / 1y / all), granularity

## File structure

```
.
├── .github/
│   └── workflows/
│       └── fetch-jira.yml   # GitHub Action (runs daily)
├── data/
│   ├── tickets.json         # Full ticket list (generated)
│   └── snapshots.json       # Daily snapshots for trend charts (generated)
├── scripts/
│   └── fetch_jira.py        # Python script that calls the Jira API
└── index.html               # The dashboard
```

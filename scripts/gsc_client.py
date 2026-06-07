"""GSC Search Analytics client — fetches query-level data for triage.py."""
import os
from datetime import date, timedelta
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

load_dotenv(os.path.join(os.path.dirname(__file__), "../credentials/.env"))

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]


def _service():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["GSC_REFRESH_TOKEN"],
        client_id=os.environ["GSC_CLIENT_ID"],
        client_secret=os.environ["GSC_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    return build("searchconsole", "v1", credentials=creds, cache_discovery=False)


def fetch_queries(site_url: str, days: int = 90, row_limit: int = 5000) -> list[dict]:
    """Return query-level rows for a GSC property over the last `days` days.

    Each row: {query, position, impressions, ctr, clicks}
    """
    end = date.today() - timedelta(days=3)   # GSC data lags ~3 days
    start = end - timedelta(days=days - 1)

    body = {
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "dimensions": ["query"],
        "rowLimit": row_limit,
    }
    resp = _service().searchanalytics().query(siteUrl=site_url, body=body).execute()
    rows = resp.get("rows", [])
    return [
        {
            "query": r["keys"][0],
            "position": r["position"],
            "impressions": r["impressions"],
            "ctr": r["ctr"],
            "clicks": r["clicks"],
        }
        for r in rows
    ]


def fetch_query_trends(site_url: str, days: int = 90) -> list[dict]:
    """Compare current vs prior period to detect position slips.

    Each row: {query, position_current, position_prior, position_delta,
               impressions, ctr, clicks}
    position_delta > 0 means rank dropped (higher number = worse).
    """
    svc = _service()
    end = date.today() - timedelta(days=3)

    def _fetch(start, end_):
        resp = svc.searchanalytics().query(
            siteUrl=site_url,
            body={
                "startDate": start.isoformat(),
                "endDate": end_.isoformat(),
                "dimensions": ["query"],
                "rowLimit": 5000,
            },
        ).execute()
        return {r["keys"][0]: r for r in resp.get("rows", [])}

    current_start = end - timedelta(days=days - 1)
    prior_end = current_start - timedelta(days=1)
    prior_start = prior_end - timedelta(days=days - 1)

    current = _fetch(current_start, end)
    prior = _fetch(prior_start, prior_end)

    results = []
    for query, row in current.items():
        if query not in prior:
            continue
        pos_now = row["position"]
        pos_then = prior[query]["position"]
        results.append({
            "query": query,
            "position_current": pos_now,
            "position_prior": pos_then,
            "position_delta": pos_now - pos_then,
            "impressions": row["impressions"],
            "ctr": row["ctr"],
            "clicks": row["clicks"],
        })
    return results


def fetch_all_page_queries(site_url: str, days: int = 90, row_limit: int = 10000) -> dict:
    """Fetch query rows grouped by page URL for the last `days` days.

    Returns {page_url: [{query, position, impressions, ctr, clicks}, ...]}
    Useful for triage: one call covers all published pages.
    """
    end = date.today() - timedelta(days=3)
    start = end - timedelta(days=days - 1)

    body = {
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "dimensions": ["page", "query"],
        "rowLimit": row_limit,
    }
    resp = _service().searchanalytics().query(siteUrl=site_url, body=body).execute()
    rows = resp.get("rows", [])

    by_page = {}
    for r in rows:
        page, query = r["keys"]
        by_page.setdefault(page, []).append({
            "query": query,
            "position": r["position"],
            "impressions": r["impressions"],
            "ctr": r["ctr"],
            "clicks": r["clicks"],
        })
    return by_page


if __name__ == "__main__":
    import yaml, sys

    cfg_path = os.path.join(os.path.dirname(__file__), "../config/sites.yaml")
    with open(cfg_path) as f:
        sites = yaml.safe_load(f)["sites"]

    site_key = sys.argv[1] if len(sys.argv) > 1 else "trainingint"
    site_url = sites[site_key]["gsc_property"]

    rows = fetch_queries(site_url, days=30)
    print(f"Fetched {len(rows)} queries for {site_url}")
    for r in rows[:10]:
        print(f"  pos={r['position']:5.1f}  impr={r['impressions']:5d}  {r['query']}")

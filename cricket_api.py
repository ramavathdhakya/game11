import os, json, requests
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()
KEY = os.getenv("BIGBALL_API_KEY") or os.getenv("BIGG_BALL_API")
HEADERS = {"Authorization": f"Bearer {KEY}"}
BASE = "https://api.bigballsdata.com"

# Start searching from this day and go backwards.
# None = start from yesterday. Or write a day like "2026-09-15".
START_DATE = None

def get(url, params=None):
    r = requests.get(url, headers=HEADERS, params=params, timeout=10)
    print("Status code:", r.status_code)
    try:
        return r.json()
    except ValueError:
        print(r.text[:500])
        return {}

if START_DATE:
    day = datetime.strptime(START_DATE, "%Y-%m-%d").date()
else:
    day = datetime.now(timezone.utc).date() - timedelta(days=1)

found = None
for _ in range(30):   # look back up to 30 days
    print(f"\nChecking {day} ...")
    data = get(f"{BASE}/v1/cricket/matches", {"date": day.isoformat()}).get("data", [])
    print("Matches:", len(data), "| statuses:", sorted({m.get("status") for m in data}))
    finished = [m for m in data if m.get("status") == "finished"]
    if finished:
        found = finished[0]
        break
    day -= timedelta(days=1)

if not found:
    print("\nNo finished match found in the last 30 days.")
    raise SystemExit

print("\n===== FIRST FINISHED MATCH (full data from the list) =====")
print(json.dumps(found, indent=2))

match_id = found["id"]
print("\n===== STATISTICS =====")
print(json.dumps(get(f"{BASE}/v1/matches/{match_id}/statistics"), indent=2)[:3000])

print("\n===== STATE =====")
print(json.dumps(get(f"{BASE}/v1/cricket/matches/{match_id}/state"), indent=2)[:3000])
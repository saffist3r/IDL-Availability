"""
Builds the static site into _site/: copies site/ and writes data.json with the
free slots of every court for the coming days. Run by the GitHub Actions
workflow on a schedule; run it locally the same way to preview.

    python scripts/build_site.py && python -m http.server -d _site 8010
"""
import json
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from club import BASE_URL, COURTS, fetch_court_slots

DAYS_AHEAD = 14
PARALLEL_REQUESTS = 6
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "_site"


def main() -> int:
    now = datetime.now(ZoneInfo("Europe/Paris"))
    days = [now.date() + timedelta(days=i) for i in range(DAYS_AHEAD)]
    jobs = [(day, court) for day in days for court in COURTS]

    def fetch(job):
        day, court = job
        try:
            return fetch_court_slots(court, day)
        except OSError as e:
            print(f"Failed {court['name']} {day}: {e}", file=sys.stderr)
            return None

    with ThreadPoolExecutor(max_workers=PARALLEL_REQUESTS) as pool:
        results = list(pool.map(fetch, jobs))

    failures = sum(r is None for r in results)
    if failures == len(jobs):
        print("The club website did not answer at all; keeping the previous deploy", file=sys.stderr)
        return 1

    availability = {day.isoformat(): {} for day in days}
    for (day, court), slots in zip(jobs, results):
        # A court that failed is left out of that day rather than shown as full
        if slots is not None:
            availability[day.isoformat()][str(court["id"])] = slots

    data = {
        "generated_at": now.isoformat(timespec="seconds"),
        "booking_base_url": BASE_URL + "/produit/",
        "courts": [{"id": c["id"], "name": c["name"], "product_slug": c["product_slug"]} for c in COURTS],
        "days": availability,
    }

    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(ROOT / "site", OUT)
    (OUT / "data.json").write_text(json.dumps(data, separators=(",", ":")))
    print(f"Wrote {len(jobs) - failures}/{len(jobs)} court-days to {OUT / 'data.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

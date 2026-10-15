"""
Keeps the free slots of every court for the coming days in memory, refreshed
in the background, and saved to disk so a restart serves data straight away.
"""
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from app import weather
from app.club import BASE_URL, COURTS, fetch_court_slots

DAYS_AHEAD = 14
PARALLEL_REQUESTS = 6
REFRESH_SECONDS = 5 * 60
NIGHT_REFRESH_SECONDS = 60 * 60
PARIS = ZoneInfo("Europe/Paris")

log = logging.getLogger("availability")


def collect() -> Optional[dict]:
    """Fetch every court for the coming days. None if the club site did not answer at all."""
    now = datetime.now(PARIS)
    days = [now.date() + timedelta(days=i) for i in range(DAYS_AHEAD)]
    jobs = [(day, court) for day in days for court in COURTS]

    def fetch(job):
        day, court = job
        try:
            return fetch_court_slots(court, day)
        except OSError as e:
            log.warning("Failed %s %s: %s", court["name"], day, e)
            return None

    with ThreadPoolExecutor(max_workers=PARALLEL_REQUESTS) as pool:
        forecast = pool.submit(weather.fetch_hourly, DAYS_AHEAD)
        results = list(pool.map(fetch, jobs))
    try:
        hourly_weather = forecast.result()
    except (OSError, ValueError, KeyError) as e:
        # The page works without weather; it just doesn't show it
        log.warning("Weather forecast failed: %s", e)
        hourly_weather = {}

    if all(r is None for r in results):
        return None

    availability = {day.isoformat(): {} for day in days}
    for (day, court), slots in zip(jobs, results):
        # A court that failed is left out of that day rather than shown as full
        if slots is not None:
            availability[day.isoformat()][str(court["id"])] = slots

    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "booking_base_url": BASE_URL + "/produit/",
        "courts": [{"id": c["id"], "name": c["name"], "product_slug": c["product_slug"]} for c in COURTS],
        "days": availability,
        "weather": hourly_weather,
    }


class Refresher:
    def __init__(self, cache_path: Path):
        self.cache_path = cache_path
        self.data: Optional[bytes] = None
        if cache_path.exists():
            self.data = cache_path.read_bytes()

    def refresh(self) -> bool:
        data = collect()
        if data is None:
            log.warning("The club website did not answer; keeping the previous data")
            return False
        self.data = json.dumps(data, separators=(",", ":")).encode()
        self.cache_path.write_bytes(self.data)
        log.info("Availability refreshed")
        return True

    def _loop(self):
        while True:
            try:
                self.refresh()
            except Exception:
                log.exception("Refresh failed")
            # Nobody books at night: refresh less often between midnight and 06:00
            hour = datetime.now(PARIS).hour
            time.sleep(NIGHT_REFRESH_SECONDS if hour < 6 else REFRESH_SECONDS)

    def start(self):
        threading.Thread(target=self._loop, name="availability-refresh", daemon=True).start()

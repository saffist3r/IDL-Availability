"""
Client for the Île de Loisirs de Cergy-Pontoise shop (WordPress + WooCommerce
Appointments). Free slots are public: the product page asks admin-ajax.php for
the slot list of one court on one day and gets back an HTML fragment.
"""
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Dict, List, Tuple

BASE_URL = "https://cergy-pontoise.iledeloisirs.fr/boutique"
AJAX_URL = BASE_URL + "/wp/wp-admin/admin-ajax.php"
USER_AGENT = "Mozilla/5.0 (Reservation IDL availability viewer)"

# Two shop products, three courts each. Court ids are the plugin's "staff" ids.
COURTS = [
    {"id": 2258, "name": "Court 1", "product_id": 23706, "product_slug": "padel"},
    {"id": 2259, "name": "Court 2", "product_id": 23706, "product_slug": "padel"},
    {"id": 2260, "name": "Court 3", "product_id": 23706, "product_slug": "padel"},
    {"id": 10064, "name": "Court 4", "product_id": 59903, "product_slug": "padel-eclaire-en-soiree"},
    {"id": 10065, "name": "Court 5", "product_id": 59903, "product_slug": "padel-eclaire-en-soiree"},
    {"id": 10066, "name": "Court 6", "product_id": 59903, "product_slug": "padel-eclaire-en-soiree"},
]

CACHE_SECONDS = 60
_SLOT_RE = re.compile(r'<li class="slot[^"]*" data-slot="(\d{4})" data-remaining="(\d+)"')
_cache: Dict[Tuple[int, str], Tuple[float, List[str]]] = {}


def booking_url(court: dict, day: date, hhmm: str) -> str:
    """Club product page with the day and hour preselected."""
    return f"{BASE_URL}/produit/{court['product_slug']}/?date={day.isoformat()}&time={hhmm}"


def _fetch_court_slots(court: dict, day: date) -> List[str]:
    """Free start times ("0800", ...) for one court on one day."""
    key = (court["id"], day.isoformat())
    cached = _cache.get(key)
    if cached and time.time() - cached[0] < CACHE_SECONDS:
        return cached[1]

    form = urllib.parse.urlencode({
        "wc_appointments_field_staff": court["id"],
        "wc_appointments_field_start_date_year": day.year,
        "wc_appointments_field_start_date_month": day.month,
        "wc_appointments_field_start_date_day": day.day,
        "add-to-cart": court["product_id"],
    })
    body = urllib.parse.urlencode({"action": "wc_appointments_get_slots", "form": form}).encode()
    request = urllib.request.Request(AJAX_URL, data=body, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=15) as response:
        html = response.read().decode("utf-8", errors="replace")

    slots = [hhmm for hhmm, remaining in _SLOT_RE.findall(html) if int(remaining) > 0]
    _cache[key] = (time.time(), slots)
    return slots


def get_availability(day: date) -> List[dict]:
    """Free slots on every court for one day, fetched in parallel."""
    with ThreadPoolExecutor(max_workers=len(COURTS)) as pool:
        results = list(pool.map(lambda c: _fetch_court_slots(c, day), COURTS))
    return [
        {
            "id": court["id"],
            "name": court["name"],
            "slots": [
                {"time": f"{s[:2]}:{s[2:]}", "booking_url": booking_url(court, day, s)}
                for s in slots
            ],
        }
        for court, slots in zip(COURTS, results)
    ]

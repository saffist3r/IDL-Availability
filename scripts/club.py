"""
Client for the Île de Loisirs de Cergy-Pontoise shop (WordPress + WooCommerce
Appointments). Free slots are public: the product page asks admin-ajax.php for
the slot list of one court on one day and gets back an HTML fragment.
"""
import re
import urllib.parse
import urllib.request
from datetime import date
from typing import List

BASE_URL = "https://cergy-pontoise.iledeloisirs.fr/boutique"
AJAX_URL = BASE_URL + "/wp/wp-admin/admin-ajax.php"
USER_AGENT = "Mozilla/5.0 (IDL-Availability padel viewer)"

# Two shop products, three courts each. Court ids are the plugin's "staff" ids.
COURTS = [
    {"id": 2258, "name": "Court 1", "product_id": 23706, "product_slug": "padel"},
    {"id": 2259, "name": "Court 2", "product_id": 23706, "product_slug": "padel"},
    {"id": 2260, "name": "Court 3", "product_id": 23706, "product_slug": "padel"},
    {"id": 10064, "name": "Court 4", "product_id": 59903, "product_slug": "padel-eclaire-en-soiree"},
    {"id": 10065, "name": "Court 5", "product_id": 59903, "product_slug": "padel-eclaire-en-soiree"},
    {"id": 10066, "name": "Court 6", "product_id": 59903, "product_slug": "padel-eclaire-en-soiree"},
]

_SLOT_RE = re.compile(r'<li class="slot[^"]*" data-slot="(\d{4})" data-remaining="(\d+)"')


def fetch_court_slots(court: dict, day: date) -> List[str]:
    """Free start times ("0800", ...) for one court on one day."""
    form = urllib.parse.urlencode({
        "wc_appointments_field_staff": court["id"],
        "wc_appointments_field_start_date_year": day.year,
        "wc_appointments_field_start_date_month": day.month,
        "wc_appointments_field_start_date_day": day.day,
        "add-to-cart": court["product_id"],
    })
    body = urllib.parse.urlencode({"action": "wc_appointments_get_slots", "form": form}).encode()
    request = urllib.request.Request(AJAX_URL, data=body, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=20) as response:
        html = response.read().decode("utf-8", errors="replace")
    return [hhmm for hhmm, remaining in _SLOT_RE.findall(html) if int(remaining) > 0]

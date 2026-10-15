# Réservation Padel IDL

A phone-friendly page showing free padel slots on the 6 courts of the Île de Loisirs de Cergy-Pontoise, for sharing with friends. Tapping a court opens the club's booking page with that day and hour preselected.

The club shop runs WordPress + WooCommerce Appointments. Free slots are public: `admin-ajax.php` with `action=wc_appointments_get_slots` returns the slots for one court on one day. Results are cached for 60 seconds.

| Product | Product id | Courts (staff ids) |
|---|---|---|
| Padel 1, 2, 3 (`/produit/padel/`) | 23706 | 2258, 2259, 2260 |
| Padel 4, 5, 6 (`/produit/padel-eclaire-en-soiree/`) | 59903 | 10064, 10065, 10066 |

## Run locally

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --port 8010 --reload
```

Open http://localhost:8010.

## API

`GET /api/availability?date=YYYY-MM-DD` returns each court with its free slots and a booking link. Dates must be within the next 60 days.

## Next: one-tap booking

When logged in, the product form also takes `addon-inviter-des-joueurs-<pid>-1[]` and `addon-email-du-joueur-{1,2,3}-<pid>-{2,3,4}`. Inviting subscribed players makes the booking free. The checkout step after add-to-cart has not been captured yet.

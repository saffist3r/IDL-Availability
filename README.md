# IDL Availability

A phone-friendly page (in French) showing free 2-hour padel slots — two consecutive free hours on the same court — on the 6 courts of the Île de Loisirs de Cergy-Pontoise, for sharing with friends. Tapping a court opens the club's booking page with that day and hour preselected.

Live at https://padel.saffist3r.xyz (the old GitHub Pages link redirects there).

## How it works

The club shop runs WordPress + WooCommerce Appointments. Free slots are public: `admin-ajax.php` with `action=wc_appointments_get_slots` returns the slots for one court on one day. The club site does not allow browsers on other sites to call it, so the page cannot ask it directly.

A small FastAPI app ([server/app](server/app)) runs on the saffist3r.xyz Kubernetes cluster. In the background it fetches the next 14 days for every court every 15 minutes (hourly at night), keeps the result in memory and on disk, and serves it as `/data.json` along with the page in [site/](site/). Slots can be up to ~15 minutes old; the club page shows the truth when you tap through.

Each 2-hour row also shows the weather for those hours (courts are outdoor), from the free [Open-Meteo](https://open-meteo.com) hourly forecast for the padel courts themselves (49.028824, 2.058013, from the club's activity map), fetched in the same refresh. The worst of the two hours is shown, and rows where rain is likely (≥ 50 % chance or ≥ 0.3 mm) are tinted blue.

| Product | Product id | Courts (staff ids) |
|---|---|---|
| Padel 1, 2, 3 (`/produit/padel/`) | 23706 | 2258, 2259, 2260 |
| Padel 4, 5, 6 (`/produit/padel-eclaire-en-soiree/`) | 59903 | 10064, 10065, 10066 |

## Usage stats

The page sends small anonymous events (page opened, day/filter picked, slot tapped) to `/api/events`, stored in SQLite. No cookies or IP addresses are stored; a visitor is a random id kept in the phone's localStorage. Nothing is sent when the page runs on localhost.

Dashboard: https://padel.saffist3r.xyz/admin (user `admin`, password in the `stats-auth` secret; `server/deploy.sh` prints the command to read it).

## Run locally

```bash
python3 -m venv .venv
.venv/bin/pip install -r server/requirements.txt
STATS_PASSWORD=local .venv/bin/uvicorn --app-dir server app.main:app --port 8010 --reload
```

Open http://localhost:8010 (slots appear about 30 seconds after the first start).

## Deploy

```bash
./server/deploy.sh
```

It builds the image inside minikube on the server, applies [server/k8s/padel-idl.yaml](server/k8s/padel-idl.yaml), and on first run gets a Let's Encrypt certificate the same way as the other saffist3r.xyz apps.

## Next: one-tap booking

When logged in, the product form also takes `addon-inviter-des-joueurs-<pid>-1[]` and `addon-email-du-joueur-{1,2,3}-<pid>-{2,3,4}`. Inviting subscribed players makes the booking free. The checkout step after add-to-cart has not been captured yet. Booking needs the booker's club login, so it will need a small server rather than GitHub Pages.

# IDL Availability

A phone-friendly page (in French) showing free 2-hour padel slots — two consecutive free hours on the same court — on the 6 courts of the Île de Loisirs de Cergy-Pontoise, for sharing with friends. Tapping a court opens the club's booking page with that day and hour preselected.

Live at https://saffist3r.github.io/IDL-Availability/

## How it works

The club shop runs WordPress + WooCommerce Appointments. Free slots are public: `admin-ajax.php` with `action=wc_appointments_get_slots` returns the slots for one court on one day. The club site does not allow browsers on other sites to call it, so the page cannot ask it directly.

Instead, a GitHub Actions workflow ([deploy.yml](.github/workflows/deploy.yml)) runs every 15 minutes from about 06:00 to midnight. It fetches the next 14 days for every court, writes `data.json` and publishes the site to GitHub Pages. Slots can therefore be up to ~15–20 minutes old; the club page shows the truth when you tap through.

| Product | Product id | Courts (staff ids) |
|---|---|---|
| Padel 1, 2, 3 (`/produit/padel/`) | 23706 | 2258, 2259, 2260 |
| Padel 4, 5, 6 (`/produit/padel-eclaire-en-soiree/`) | 59903 | 10064, 10065, 10066 |

## Usage stats

The page sends small anonymous events (page opened, day/filter picked, slot tapped) to a stats service at https://padel.saffist3r.xyz, which keeps them in SQLite. No cookies or IP addresses are stored; a visitor is a random id kept in the phone's localStorage. Nothing is sent when the page runs on localhost.

- Dashboard: https://padel.saffist3r.xyz/stats (user `admin`, password stored in the `stats-auth` secret; `server/deploy.sh` prints the command to read it)
- Code: [server/](server/) (FastAPI). Deploy or update with `./server/deploy.sh`: it builds the image inside minikube on the server, applies [server/k8s/padel-idl.yaml](server/k8s/padel-idl.yaml), and on first run gets a Let's Encrypt certificate the same way as the other saffist3r.xyz apps.

## Run locally

No dependencies beyond Python 3.9+.

```bash
python3 scripts/build_site.py
python3 -m http.server -d _site 8010
```

Open http://localhost:8010.

## Next: one-tap booking

When logged in, the product form also takes `addon-inviter-des-joueurs-<pid>-1[]` and `addon-email-du-joueur-{1,2,3}-<pid>-{2,3,4}`. Inviting subscribed players makes the booking free. The checkout step after add-to-cart has not been captured yet. Booking needs the booker's club login, so it will need a small server rather than GitHub Pages.

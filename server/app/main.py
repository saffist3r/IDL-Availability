"""
Usage stats for the padel availability page. The page (on GitHub Pages) sends
small events here; /stats shows them behind a password. No IP addresses or
cookies are stored: a visitor is a random id the page keeps in localStorage.
"""
import json
import os
import re
import secrets
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field, ValidationError

DB_PATH = Path(os.environ.get("DB_PATH", "data/stats.db"))
STATS_USER = os.environ.get("STATS_USER", "admin")
STATS_PASSWORD = os.environ.get("STATS_PASSWORD", "")
ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS", "https://saffist3r.github.io,http://localhost:8010"
).split(",")
EVENT_TYPES = {"view", "day", "period", "slot_click"}
BOT_RE = re.compile(r"bot|crawl|spider|preview|facebookexternalhit|whatsapp|slurp|curl|python|headless", re.I)
PARIS = ZoneInfo("Europe/Paris")

app = FastAPI(title="Padel IDL stats", docs_url=None, redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_methods=["POST"], allow_headers=["*"])
security = HTTPBasic()


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.on_event("startup")
def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(db()) as conn, conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY,
                at TEXT NOT NULL,
                type TEXT NOT NULL,
                visitor TEXT NOT NULL,
                device TEXT,
                props TEXT
            )"""
        )
        conn.execute("CREATE INDEX IF NOT EXISTS events_at ON events(at)")


class Event(BaseModel):
    type: str = Field(..., max_length=20)
    visitor: str = Field(..., min_length=8, max_length=40)
    props: dict = Field(default_factory=dict)


def device_of(user_agent: str) -> str:
    ua = user_agent.lower()
    if "iphone" in ua or "ipad" in ua:
        return "iPhone"
    if "android" in ua:
        return "Android"
    if "mac os" in ua or "windows" in ua or "linux" in ua:
        return "Ordinateur"
    return "Autre"


@app.post("/api/events", status_code=204)
async def record_event(request: Request):
    # Sent with navigator.sendBeacon as text/plain (no CORS preflight), so parse by hand
    raw = await request.body()
    if len(raw) > 2000:
        raise HTTPException(status_code=413)
    try:
        event = Event(**json.loads(raw))
    except (ValueError, ValidationError):
        raise HTTPException(status_code=400, detail="Invalid event")
    if event.type not in EVENT_TYPES:
        raise HTTPException(status_code=400, detail="Unknown event type")

    user_agent = request.headers.get("user-agent", "")
    if BOT_RE.search(user_agent):
        return Response(status_code=204)

    props = {str(k)[:20]: str(v)[:40] for k, v in list(event.props.items())[:6]}
    with closing(db()) as conn, conn:
        conn.execute(
            "INSERT INTO events (at, type, visitor, device, props) VALUES (?, ?, ?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(timespec="seconds"), event.type, event.visitor,
             device_of(user_agent), json.dumps(props, ensure_ascii=False)),
        )
    return Response(status_code=204)


@app.get("/api/health")
def health():
    return {"status": "ok"}


def require_admin(credentials: HTTPBasicCredentials = Depends(security)):
    ok = STATS_PASSWORD and secrets.compare_digest(credentials.username, STATS_USER) \
        and secrets.compare_digest(credentials.password, STATS_PASSWORD)
    if not ok:
        raise HTTPException(status_code=401, headers={"WWW-Authenticate": "Basic"})


def _rows(conn, sql, *params):
    return [tuple(r) for r in conn.execute(sql, params).fetchall()]


def _table(title: str, headers, rows, empty="Pas encore de données") -> str:
    if not rows:
        body = f'<tr><td colspan="{len(headers)}" class="muted">{empty}</td></tr>'
    else:
        body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    head = "".join(f"<th>{h}</th>" for h in headers)
    return f"<section><h2>{title}</h2><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></section>"


@app.get("/stats", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
def stats(days: Optional[int] = 30):
    days = max(1, min(days or 30, 365))
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
    # Group by the Paris calendar day, not UTC
    offset = datetime.now(PARIS).utcoffset().total_seconds() / 3600
    local_day = f"date(at, '{offset:+.0f} hours')"

    with closing(db()) as conn:
        totals = conn.execute(
            """SELECT COUNT(DISTINCT visitor),
                      COUNT(*) FILTER (WHERE type = 'view'),
                      COUNT(*) FILTER (WHERE type = 'slot_click'),
                      COUNT(DISTINCT CASE WHEN type = 'slot_click' THEN visitor END)
               FROM events WHERE at >= ?""", (since,)).fetchone()
        per_day = _rows(conn, f"""SELECT {local_day} AS d, COUNT(DISTINCT visitor),
                                        COUNT(*) FILTER (WHERE type = 'view'),
                                        COUNT(*) FILTER (WHERE type = 'slot_click')
                                 FROM events WHERE at >= ? GROUP BY d ORDER BY d DESC""", since)
        slots = _rows(conn, """SELECT json_extract(props, '$.slot'), COUNT(*), COUNT(DISTINCT visitor)
                               FROM events WHERE type = 'slot_click' AND at >= ?
                               GROUP BY 1 ORDER BY 2 DESC LIMIT 15""", since)
        weekdays = _rows(conn, """SELECT json_extract(props, '$.weekday'), COUNT(*)
                                  FROM events WHERE type = 'slot_click' AND at >= ?
                                  GROUP BY 1 ORDER BY 2 DESC""", since)
        courts = _rows(conn, """SELECT json_extract(props, '$.court'), COUNT(*)
                                FROM events WHERE type = 'slot_click' AND at >= ?
                                GROUP BY 1 ORDER BY 2 DESC""", since)
        periods = _rows(conn, """SELECT json_extract(props, '$.period'), COUNT(*)
                                 FROM events WHERE type = 'period' AND at >= ?
                                 GROUP BY 1 ORDER BY 2 DESC""", since)
        devices = _rows(conn, """SELECT device, COUNT(DISTINCT visitor)
                                 FROM events WHERE at >= ? GROUP BY 1 ORDER BY 2 DESC""", since)

    visitors, views, clicks, bookers = totals
    period_names = {"all": "Tout", "morning": "Matin", "afternoon": "Après-midi", "evening": "Soir"}
    periods = [(period_names.get(p, p), n) for p, n in periods]
    range_links = " · ".join(
        f'<a href="?days={d}"{" class=on" if d == days else ""}>{label}</a>'
        for d, label in ((7, "7 jours"), (30, "30 jours"), (90, "90 jours"), (365, "1 an"))
    )

    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Stats Padel IDL</title>
<style>
:root {{ --bg:#f4f6f5; --card:#fff; --text:#14211f; --muted:#5d6b68; --border:#dde3e1; --accent:#0f766e; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#0e1513; --card:#17211f; --text:#e8efed; --muted:#9aaaa6; --border:#2a3835; --accent:#2dd4bf; }} }}
* {{ box-sizing:border-box; }}
body {{ margin:0 auto; max-width:760px; padding:20px 16px 40px; background:var(--bg); color:var(--text);
       font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }}
h1 {{ font-size:1.4rem; margin:0 0 4px; }} h2 {{ font-size:1rem; margin:0 0 8px; }}
.range {{ color:var(--muted); font-size:.9rem; margin-bottom:16px; }}
.range a {{ color:var(--muted); }} .range a.on {{ color:var(--accent); font-weight:700; text-decoration:none; }}
.kpis {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:8px; margin-bottom:16px; }}
.kpi, section {{ background:var(--card); border:1px solid var(--border); border-radius:12px; padding:12px 14px; }}
.kpi b {{ display:block; font-size:1.6rem; }} .kpi span {{ color:var(--muted); font-size:.85rem; }}
section {{ margin-bottom:12px; overflow-x:auto; }}
table {{ width:100%; border-collapse:collapse; font-size:.9rem; }}
th {{ text-align:left; color:var(--muted); font-weight:600; }}
th, td {{ padding:6px 8px 6px 0; border-bottom:1px solid var(--border); }}
tr:last-child td {{ border-bottom:none; }} .muted {{ color:var(--muted); }}
</style></head><body>
<h1>Stats Padel IDL</h1>
<div class="range">{range_links}</div>
<div class="kpis">
  <div class="kpi"><b>{visitors}</b><span>visiteurs uniques</span></div>
  <div class="kpi"><b>{views}</b><span>visites de la page</span></div>
  <div class="kpi"><b>{clicks}</b><span>clics vers le club</span></div>
  <div class="kpi"><b>{bookers}</b><span>visiteurs ayant cliqué</span></div>
</div>
{_table("Par jour", ["Jour", "Visiteurs", "Visites", "Clics"], per_day)}
{_table("Créneaux les plus demandés", ["Créneau", "Clics", "Visiteurs"], slots)}
{_table("Jours les plus demandés", ["Jour", "Clics"], weekdays)}
{_table("Terrains choisis", ["Terrain", "Clics"], courts)}
{_table("Filtres utilisés", ["Filtre", "Fois"], periods)}
{_table("Appareils", ["Appareil", "Visiteurs"], devices)}
</body></html>"""

from datetime import date, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import club

MAX_DAYS_AHEAD = 60
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Réservation Padel IDL")


@app.get("/api/availability")
def availability(day: date = Query(..., alias="date")):
    today = date.today()
    if day < today or day > today + timedelta(days=MAX_DAYS_AHEAD):
        raise HTTPException(status_code=400, detail=f"Date must be within the next {MAX_DAYS_AHEAD} days")
    try:
        courts = club.get_availability(day)
    except OSError:
        raise HTTPException(status_code=502, detail="The club website did not answer")
    return {"date": day.isoformat(), "courts": courts}


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

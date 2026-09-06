from datetime import datetime, date
from pathlib import Path
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, String, Integer, Float, DateTime, Text, ForeignKey, select, Date
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session

DB = "sqlite:////data/batteries.db"
engine = create_engine(DB, connect_args={"check_same_thread": False})
app = FastAPI(title="Battery Logbook")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

class Base(DeclarativeBase):
    pass

class Battery(Base):
    __tablename__ = "batteries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chemistry: Mapped[str] = mapped_column(String(50))
    brand: Mapped[str] = mapped_column(String(100), default="")
    size: Mapped[str] = mapped_column(String(100), default="")
    capacity_rated: Mapped[float | None] = mapped_column(Float, nullable=True)
    purchase_date: Mapped[date] = mapped_column(Date, default=datetime.now().date())
    location: Mapped[str] = mapped_column(String(200), default="")
    notes: Mapped[str] = mapped_column(Text, default="")

class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    battery_id: Mapped[int] = mapped_column(ForeignKey("batteries.id"))
    event_date: Mapped[date] = mapped_column(Date, default=datetime.now().date())
    event_type: Mapped[str] = mapped_column(String(50))
    capacity_measured: Mapped[float | None] = mapped_column(Float, nullable=True)
    location: Mapped[str] = mapped_column(String(200), default="")
    notes: Mapped[str] = mapped_column(Text, default="")

Base.metadata.create_all(engine)

EVENT_TYPES = ["Charge", "Break-in", "Refresh", "Storage", "Put into use", "Removed from use", "Other"]

def redirect(url): return RedirectResponse(url, status_code=303)

@app.get("/", response_class=HTMLResponse)
def home(request: Request, q: str = ""):
    with (Session(engine) as s):
        stmt = select(Battery).order_by(Battery.id)
        batteries = s.scalars(stmt).all()
        if q:
            batteries = [b for b in batteries
                         if q.lower() in str(b.id).lower()
                         or q.lower() in b.brand.lower()
                         or q.lower() in b.size.lower()
                         or q.lower() in b.location.lower()
                         or q.lower() in b.notes.lower()
                         or q.lower() in b.chemistry.lower()]

        # Battery health calculation:
        # Get all capacity measurements, newest first
        capacity_events = s.scalars(
            select(Event)
            .where(Event.capacity_measured.is_not(None))
            .order_by(Event.event_date.desc())
        )

        # Keep only the latest measurement for each battery
        last_measured = {}
        for event in capacity_events:
            if event.battery_id not in last_measured:
                last_measured[event.battery_id] = event.capacity_measured

        # Calculate battery health:
        for b in batteries:
            measured = last_measured.get(b.id)

            if b.capacity_rated and measured is not None:
                b.health = measured / b.capacity_rated * 100
            else:
                b.health = None

        # Get list of recent events
        recent = s.scalars(
            select(Event)
            .order_by(Event.event_date.desc())
            .limit(10)
        ).all()

        return templates.TemplateResponse("index.html", {"request":request,"batteries":batteries,
            "recent":recent,"q":q,"event_types":EVENT_TYPES})

@app.get("/battery/{bid}", response_class=HTMLResponse)
def battery(request: Request, bid: int):
    with Session(engine) as s:
        b=s.get(Battery,bid)
        if not b: raise HTTPException(404)
        events=s.scalars(select(Event).where(Event.battery_id==bid).order_by(Event.event_date.desc())).all()
        return templates.TemplateResponse("battery.html", {"request":request,"b":b,"events":events,
            "event_types":EVENT_TYPES})

@app.post("/battery/new")
def new_battery(chemistry=Form(...), brand=Form(""), size=Form(""), capacity_rated=Form(""),
                purchase_date=Form(""), notes=Form(""), location=Form("")):
    purchase_date = datetime.strptime(purchase_date, '%Y-%m-%d').date()
    with Session(engine) as s:
        b=Battery(chemistry=chemistry,
                  brand=brand,
                  size=size,
                  capacity_rated=float(capacity_rated) if capacity_rated else None,
                  purchase_date=purchase_date,
                  location=location,
                  notes=notes)
        s.add(b); s.commit(); bid=b.id
        s.add(Event(battery_id=bid,event_type="Created",notes="Battery added to logbook")); s.commit()
    return redirect(f"/battery/{bid}")

@app.post("/battery/{bid}/event")
def add_event(bid:int, event_type=Form(...), event_date=Form(""), capacity_measured=Form(""),
              location=Form(""), notes=Form("")):
    event_date = datetime.strptime(event_date, '%Y-%m-%d').date() if date else datetime.now().date
    with Session(engine) as s:
        b=s.get(Battery,bid)
        if not b: raise HTTPException(404)
        e=Event(battery_id=bid,
                event_date=event_date,
                event_type=event_type,
                capacity_measured=float(capacity_measured) if capacity_measured else None,
                location=location,
                notes=notes)
        s.add(e)
        if event_type == "Put into use" and location: b.location=location
        elif event_type == "Removed from use": b.location=""
        elif event_type in ("Storage","Put into use") and location: b.location=location if event_type=="Put into use" else b.location
        s.commit()
    return redirect(f"/battery/{bid}")

@app.post("/battery/{bid}/update")
def update_battery(bid:int, chemistry=Form(...), brand=Form(""), size=Form(""), capacity_rated=Form(""),
                   purchase_date=Form(""), notes=Form("")):
    purchase_date = datetime.strptime(purchase_date, '%Y-%m-%d').date()
    with Session(engine) as s:
        b=s.get(Battery,bid)
        if not b: raise HTTPException(404)
        b.chemistry=chemistry
        b.brand=brand
        b.size=size
        b.capacity_rated=float(capacity_rated) if capacity_rated else None
        b.purchase_date=purchase_date;b.notes=notes
        s.commit()
    return redirect(f"/battery/{bid}")



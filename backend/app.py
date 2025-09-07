# backend/app.py
from datetime import date
from io import StringIO
from typing import List, Dict, Tuple
import csv, random, os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Date, ForeignKey,
    select, func, delete
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, Session

# ----------------------
# Settings / DB URL resolution
# ----------------------
class Settings(BaseSettings):
    # Keep only defaults here; selection logic is below
    DB_URL: str = "sqlite:///./kam.db"
    APP_ENV: str = "local"
    model_config = SettingsConfigDict(extra="ignore", env_prefix="", case_sensitive=False)

# Prefer DATABASE_URL (Dokku Postgres), else DB_URL, else SQLite
resolved_db_url = os.getenv("DATABASE_URL") or os.getenv("DB_URL") or "sqlite:///./kam.db"

# SQLAlchemy 2.x requires 'postgresql://' not 'postgres://'
if resolved_db_url.startswith("postgres://"):
    resolved_db_url = resolved_db_url.replace("postgres://", "postgresql://", 1)

settings = Settings(DB_URL=resolved_db_url, _env_file=".env", _env_file_encoding="utf-8")

print(f"Using DB: {settings.DB_URL} (APP_ENV={settings.APP_ENV})")

# ----------------------
# ORM Base & Models
# ----------------------
class Base(DeclarativeBase):
    pass

class KAM(Base):
    __tablename__ = "kams"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    region: Mapped[str] = mapped_column(String, default="EU")
    targets: Mapped[List["MonthlyTarget"]] = relationship(
        back_populates="kam", cascade="all, delete-orphan"
    )
    projects: Mapped[List["Project"]] = relationship(
        back_populates="kam", cascade="all, delete-orphan"
    )

class MonthlyTarget(Base):
    __tablename__ = "monthly_targets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kam_id: Mapped[int] = mapped_column(ForeignKey("kams.id"))
    month: Mapped[date] = mapped_column(Date)
    target_pp: Mapped[float] = mapped_column(Float)
    target_lvp: Mapped[float] = mapped_column(Float)
    kam: Mapped[KAM] = relationship(back_populates="targets")

class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kam_id: Mapped[int] = mapped_column(ForeignKey("kams.id"))
    code: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    kam: Mapped[KAM] = relationship(back_populates="projects")
    snapshots: Mapped[List["ProjectMonth"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )

class ProjectMonth(Base):
    __tablename__ = "project_months"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    month: Mapped[date] = mapped_column(Date)
    pp: Mapped[float] = mapped_column(Float)
    lvp: Mapped[float] = mapped_column(Float)
    sop_ym: Mapped[str] = mapped_column(String)  # YYYY-MM
    foc2026_pp: Mapped[float] = mapped_column(Float)
    foc2026_sec: Mapped[float] = mapped_column(Float)
    project: Mapped[Project] = relationship(back_populates="snapshots")

# Engine (robust for Postgres + fine for SQLite)
engine = create_engine(settings.DB_URL, echo=False, future=True, pool_pre_ping=True)
Base.metadata.create_all(engine)

# ----------------------
# FastAPI App & CORS
# ----------------------
app = FastAPI(title="KAM Rewards API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://reward.athenalabo.com",
        "https://reward.athenalabo.com",
    ],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# ----------------------
# Helpers & Schemas
# ----------------------
def month_add(d: date, n: int) -> date:
    y = d.year + (d.month - 1 + n) // 12
    m = (d.month - 1 + n) % 12 + 1
    return date(y, m, 1)

class SeedParams(BaseModel):
    start_month: date = date(2025, 9, 1)
    months: int = 4
    kam_names: List[str] = ["Alice", "Bob", "Carla", "Dario"]
    regions: List[str] = ["China Consumer", "China Industry", "JP", "TW"]
    random_seed: int = 42

class ScoreItem(BaseModel):
    kam: str
    month: date
    points_gained_pp: float
    points_gained_lvp: float
    points_lost_sop_delay: float
    points_lost_volume_dec: float
    points_lost_pp_dec: float
    total: float

class ScoreSummary(BaseModel):
    monthly: List[ScoreItem]
    cumulative_by_kam: Dict[str, float]

# ----------------------
# Seed (SQLAlchemy 2.x-safe deletes)
# ----------------------
@app.post("/seed", response_model=dict)
def seed_data(params: SeedParams):
    random.seed(params.random_seed)
    with Session(engine) as s:
        # 2.x native delete() to avoid legacy query.delete() pitfalls
        s.execute(delete(ProjectMonth))
        s.execute(delete(Project))
        s.execute(delete(MonthlyTarget))
        s.execute(delete(KAM))
        s.commit()

        # KAMs + targets
        for i, name in enumerate(params.kam_names):
            region = params.regions[i % len(params.regions)]
            kam = KAM(name=name, region=region)
            s.add(kam); s.flush()
            for mi in range(params.months):
                m = month_add(params.start_month, mi)
                s.add(MonthlyTarget(
                    kam_id=kam.id,
                    month=m,
                    target_pp=random.randint(40, 120),
                    target_lvp=random.randint(20, 80),
                ))
            s.flush()

        # projects + snapshots
        for kam in s.scalars(select(KAM)).all():
            base_projects = random.randint(2, 3)
            projects: List[Project] = []
            for p in range(base_projects):
                code = f"{kam.name[:2].upper()}-P{p+1}"
                proj = Project(kam_id=kam.id, code=code, name=f"Proj {code}")
                s.add(proj); projects.append(proj)
            s.flush()

            for mi in range(params.months):
                m = month_add(params.start_month, mi)
                # updates for existing projects
                for proj in projects:
                    pp = max(0, random.randint(30, 100) + random.randint(-20, 20))
                    lvp = max(0, random.randint(10, 60) + random.randint(-10, 20))
                    sop = month_add(date(2026, random.randint(1, 9), 1), random.choice([-1, 0, 1]))
                    s.add(ProjectMonth(
                        project_id=proj.id, month=m, pp=pp, lvp=lvp,
                        sop_ym=f"{sop.year:04d}-{sop.month:02d}",
                        foc2026_pp=round(pp * random.uniform(0.2, 0.8), 2),
                        foc2026_sec=round(lvp * random.uniform(0.3, 1.0), 2),
                    ))
                # new projects added this month
                for k in range(random.randint(2, 4)):
                    code = f"{kam.name[:2].upper()}-P{len(projects)+k+1}"
                    proj = Project(kam_id=kam.id, code=code, name=f"Proj {code}")
                    s.add(proj); s.flush()
                    pp = random.randint(20, 80)
                    lvp = random.randint(5, 40)
                    sop = date(2026, random.randint(1, 12), 1)
                    s.add(ProjectMonth(
                        project_id=proj.id, month=m, pp=pp, lvp=lvp,
                        sop_ym=f"{sop.year:04d}-{sop.month:02d}",
                        foc2026_pp=round(pp * random.uniform(0.2, 0.8), 2),
                        foc2026_sec=round(lvp * random.uniform(0.3, 1.0), 2),
                    ))
                    projects.append(proj)
        s.commit()
    return {"status": "ok"}

# ----------------------
# Scoring (as in your last version with “Remarks” updates)
# ----------------------
def calc_scores() -> Tuple[List[ScoreItem], Dict[str, float]]:
    with Session(engine) as s:
        kams = s.scalars(select(KAM)).all()
        months = sorted(s.scalars(select(func.distinct(ProjectMonth.month))).all())
        results: List[ScoreItem] = []
        cumul: Dict[str, float] = {k.name: 0.0 for k in kams}

        def kam_month_snaps(kam_id: int, m: date) -> List[ProjectMonth]:
            if m is None: return []
            stmt = select(ProjectMonth).join(Project).where(
                Project.kam_id == kam_id, ProjectMonth.month == m
            )
            return list(s.scalars(stmt).all())

        def month_targets(kam_id: int, m: date):
            return s.scalar(select(MonthlyTarget).where(
                MonthlyTarget.kam_id == kam_id, MonthlyTarget.month == m
            ))

        for mi, m in enumerate(months):
            prev_m = months[mi - 1] if mi > 0 else None

            prev_proj_map = {}
            if prev_m:
                stmt_prev = select(
                    ProjectMonth.project_id, ProjectMonth.pp, ProjectMonth.lvp,
                    ProjectMonth.sop_ym, ProjectMonth.foc2026_sec
                ).where(ProjectMonth.month == prev_m)
                for pid, ppp, plvp, psop, pfoc in s.execute(stmt_prev):
                    prev_proj_map[pid] = {
                        "pp": ppp or 0.0, "lvp": plvp or 0.0,
                        "sop": psop, "foc": pfoc or 0.0
                    }

            for kam in kams:
                snaps = kam_month_snaps(kam.id, m)
                if not snaps:
                    continue

                sum_pp = sum(x.pp for x in snaps)
                sum_lvp = sum(x.lvp for x in snaps)
                prev_snaps = kam_month_snaps(kam.id, prev_m) if prev_m else []
                prev_pp = sum(x.pp for x in prev_snaps) if prev_snaps else 0.0
                prev_lvp = sum(x.lvp for x in prev_snaps) if prev_snaps else 0.0

                added_pp = max(0.0, sum_pp - prev_pp)
                added_lvp = max(0.0, sum_lvp - prev_lvp)

                t = month_targets(kam.id, m)
                gained_pp_points = 0.0
                gained_lvp_points = 0.0
                if t:
                    if added_pp >= t.target_pp * 1.3: gained_pp_points = 20.0
                    elif added_pp >= t.target_pp:     gained_pp_points = 10.0
                    if added_lvp >= t.target_lvp * 1.3: gained_lvp_points = 40.0
                    elif added_lvp >= t.target_lvp:     gained_lvp_points = 20.0

                # SOP delay
                sop_delay_loss = 0.0
                if prev_m:
                    stmt_curr = select(ProjectMonth.project_id, ProjectMonth.sop_ym).where(ProjectMonth.month == m)
                    for pid, sop_ym in s.execute(stmt_curr):
                        prev = prev_proj_map.get(pid)
                        if not prev: continue
                        def ym_to_int(ym: str) -> int:
                            y, mm = ym.split("-"); return int(y)*12 + int(mm)
                        diff = ym_to_int(sop_ym) - ym_to_int(prev["sop"])
                        if diff > 0 and prev["foc"] > 0:
                            sop_delay_loss += 2.0 * prev["foc"] * diff

                # Volume decrease (secured)
                vol_dec_loss = 0.0
                if prev_m:
                    prev_foc_total = sum(x.foc2026_sec for x in prev_snaps) if prev_snaps else 0.0
                    curr_foc_total = sum(x.foc2026_sec for x in snaps)
                    if curr_foc_total < prev_foc_total:
                        vol_dec_loss = 2.0 * (prev_foc_total - curr_foc_total)

                # PP decrease with actual promotions
                promotions = 0.0
                if prev_m:
                    stmt_curr2 = select(ProjectMonth.project_id, ProjectMonth.lvp).where(ProjectMonth.month == m)
                    for pid, lvp_now in s.execute(stmt_curr2):
                        prev = prev_proj_map.get(pid)
                        if not prev: continue
                        lift_inc = max(0.0, (lvp_now or 0.0) - prev["lvp"])
                        promotions += min(lift_inc, prev["pp"])  # cap by prev PP
                pp_dec_loss = 0.0
                if prev_m:
                    left = prev_pp + added_pp        # assessment side (put LVP back)
                    right = sum_pp + promotions      # observed side with promotions added back
                    if right < left:
                        pp_dec_loss = 2.0 * (left - right)

                # Inactivity penalty (no new projects created this month)
                inactivity_loss = 0.0
                if prev_m:
                    prev_ids = {x.project_id for x in prev_snaps}
                    curr_ids = {x.project_id for x in snaps}
                    if len(curr_ids - prev_ids) == 0:
                        inactivity_loss = 100.0

                total = (
                    gained_pp_points + gained_lvp_points
                    - (sop_delay_loss + vol_dec_loss + pp_dec_loss + inactivity_loss)
                )
                cumul[kam.name] += total

                results.append(ScoreItem(
                    kam=kam.name, month=m,
                    points_gained_pp=gained_pp_points,
                    points_gained_lvp=gained_lvp_points,
                    points_lost_sop_delay=sop_delay_loss,
                    points_lost_volume_dec=vol_dec_loss,
                    points_lost_pp_dec=pp_dec_loss,
                    total=total
                ))

        return results, cumul

# ----------------------
# API Routes
# ----------------------
@app.get("/scores", response_model=ScoreSummary)
def scores():
    m, c = calc_scores()
    return ScoreSummary(monthly=m, cumulative_by_kam=c)

@app.get("/state", response_model=dict)
def state():
    with Session(engine) as s:
        kams = [dict(id=k.id, name=k.name, region=k.region) for k in s.scalars(select(KAM)).all()]
        months = [str(m) for m in sorted(s.scalars(select(func.distinct(ProjectMonth.month))).all())]
        return {"kams": kams, "months": months}

# CSVs
@app.get("/scores_csv")
def scores_csv():
    m, _ = calc_scores()
    out = StringIO(); w = csv.writer(out)
    w.writerow(["kam","month","points_gained_pp","points_gained_lvp","points_lost_sop_delay","points_lost_volume_dec","points_lost_pp_dec","total"])
    for r in m:
        w.writerow([r.kam, r.month.isoformat(), r.points_gained_pp, r.points_gained_lvp, r.points_lost_sop_delay, r.points_lost_volume_dec, r.points_lost_pp_dec, r.total])
    return Response(out.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="monthly_scores.csv"'})

@app.get("/scores_cumulative_csv")
def scores_cumulative_csv():
    _, c = calc_scores()
    out = StringIO(); w = csv.writer(out); w.writerow(["kam","cumulative_total"])
    for k, v in c.items(): w.writerow([k, v])
    return Response(out.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="cumulative_scores.csv"'})

# Dataset & Inputs
def _row_source(name:str) -> str:
    return "manual" if (name or "").startswith("Manual ") else "seed"

@app.get("/dataset", response_model=dict)
def dataset():
    rows = []
    with Session(engine) as s:
        stmt = (
            select(
                KAM.name, Project.code, Project.name,
                ProjectMonth.month, ProjectMonth.pp, ProjectMonth.lvp,
                ProjectMonth.sop_ym, ProjectMonth.foc2026_pp, ProjectMonth.foc2026_sec
            )
            .join(Project, Project.kam_id == KAM.id)
            .join(ProjectMonth, ProjectMonth.project_id == Project.id)
            .order_by(ProjectMonth.month, KAM.name, Project.code)
        )
        for kam_name, code, pname, m, pp, lvp, sop, fpp, fsec in s.execute(stmt):
            rows.append(dict(
                kam=kam_name, project_code=code, project_name=pname, month=str(m),
                pp=pp, lvp=lvp, sop_ym=sop, foc2026_pp=fpp, foc2026_sec=fsec,
                source=_row_source(pname)
            ))
    return {"rows": rows, "count": len(rows)}

@app.get("/dataset_csv")
def dataset_csv():
    d = dataset(); out = StringIO(); w = csv.writer(out)
    w.writerow(["kam","project_code","project_name","month","pp","lvp","sop_ym","foc2026_pp","foc2026_sec","source"])
    for r in d["rows"]:
        w.writerow([r["kam"], r["project_code"], r["project_name"], r["month"], r["pp"], r["lvp"], r["sop_ym"], r["foc2026_pp"], r["foc2026_sec"], r["source"]])
    return Response(out.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="dataset_all_rows.csv"'})

@app.get("/inputs", response_model=dict)
def inputs():
    all_rows = dataset()["rows"]
    filtered = [r for r in all_rows if r["source"]=="manual" and "2026-01-01" <= r["month"] <= "2026-04-01"]
    return {"rows": filtered, "count": len(filtered)}

@app.get("/inputs_csv")
def inputs_csv():
    d = inputs(); out = StringIO(); w = csv.writer(out)
    w.writerow(["kam","project_code","project_name","month","pp","lvp","sop_ym","foc2026_pp","foc2026_sec"])
    for r in d["rows"]:
        w.writerow([r["kam"], r["project_code"], r["project_name"], r["month"], r["pp"], r["lvp"], r["sop_ym"], r["foc2026_pp"], r["foc2026_sec"]])
    return Response(out.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="inputs_manual_rows.csv"'})

# Input month
class InputMonthPayload(BaseModel):
    kam_name: str
    month: date
    new_projects: int = 2
    added_pp: float
    added_lvp: float
    avg_sop_month: int = 6
    foc_ratio_pp: float = 0.5
    foc_ratio_lvp: float = 0.7

@app.post("/input_month", response_model=dict)
def input_month(payload: InputMonthPayload):
    if not (date(2026,1,1) <= payload.month <= date(2026,4,1)):
        raise HTTPException(status_code=400, detail="Month must be 2026-01-01 to 2026-04-01 (first of month).")
    if payload.new_projects < 1:
        raise HTTPException(status_code=400, detail="new_projects must be >= 1")

    with Session(engine) as s:
        kam = s.scalar(select(KAM).where(KAM.name == payload.kam_name))
        if not kam:
            raise HTTPException(status_code=404, detail=f"KAM '{payload.kam_name}' not found.")

        t = s.scalar(select(MonthlyTarget).where(
            MonthlyTarget.kam_id == kam.id, MonthlyTarget.month == payload.month
        ))
        if not t:
            last_t = s.scalar(select(MonthlyTarget).where(
                MonthlyTarget.kam_id == kam.id
            ).order_by(MonthlyTarget.month.desc()))
            if last_t:
                t = MonthlyTarget(kam_id=kam.id, month=payload.month,
                                  target_pp=last_t.target_pp, target_lvp=last_t.target_lvp)
            else:
                t = MonthlyTarget(kam_id=kam.id, month=payload.month, target_pp=80.0, target_lvp=40.0)
            s.add(t); s.flush()

        n = payload.new_projects
        split_pp  = [round(payload.added_pp/n, 2)  for _ in range(n)]
        split_lvp = [round(payload.added_lvp/n, 2) for _ in range(n)]

        created = 0
        for i in range(n):
            code = f"{kam.name[:2].upper()}-M{payload.month.month:02d}-{random.randint(1000,9999)}"
            proj = Project(kam_id=kam.id, code=code, name=f"Manual {code}")
            s.add(proj); s.flush()

            sop = date(2026, max(1, min(12, payload.avg_sop_month)), 1)
            foc_pp  = round(split_pp[i]  * max(0.0, min(1.0, payload.foc_ratio_pp)),  2)
            foc_sec = round(split_lvp[i] * max(0.0, min(1.0, payload.foc_ratio_lvp)), 2)

            s.add(ProjectMonth(
                project_id=proj.id, month=payload.month,
                pp=split_pp[i], lvp=split_lvp[i], sop_ym=f"{sop.year:04d}-{sop.month:02d}",
                foc2026_pp=foc_pp, foc2026_sec=foc_sec
            ))
            created += 1

        s.commit()
        return {
            "status": "ok", "kam": kam.name, "month": str(payload.month),
            "projects_created": created, "added_pp": payload.added_pp, "added_lvp": payload.added_lvp
        }

@app.get("/")
def root():
    return {"ok": True, "service": "KAM Rewards API"}

import calendar
import os
from datetime import date, datetime

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import (Column, Date, DateTime, ForeignKey, Integer, String,
                        UniqueConstraint, create_engine, delete, select)
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()  # reads .env if it exists
DB_FILE = os.getenv("HABIT_DB", "habits.db")
engine = create_engine(f"sqlite:///{DB_FILE}")
Session = sessionmaker(bind=engine)
Base = declarative_base()

NUM_HABITS = 10
DEFAULT_HABITS = [
    "Drink water", "Workout", "Read 20 minutes", "Meditate", "Sleep early",
    "Journal", "Walk 10k steps", "No junk food", "Study", "Stretch",
]


class Habit(Base):
    """One of the 10 habit rows of a month's sheet."""
    __tablename__ = "habits"
    id = Column(Integer, primary_key=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    slot = Column(Integer, nullable=False)  # row number 1..10
    name = Column(String, nullable=False, default="")
    goal = Column(Integer, nullable=False, default=20)  # target days this month
    created_at = Column(DateTime, default=datetime.now)
    __table_args__ = (UniqueConstraint("year", "month", "slot"),)


class HabitLog(Base):
    """A row here = this habit was ticked on this day."""
    __tablename__ = "habit_logs"
    id = Column(Integer, primary_key=True)
    habit_id = Column(Integer, ForeignKey("habits.id"), nullable=False)
    log_date = Column(Date, nullable=False)
    __table_args__ = (UniqueConstraint("habit_id", "log_date"),)


def init_db():
    Base.metadata.create_all(engine)


def get_month_habits(year: int, month: int):
    """Return [(habit_id, slot, name, goal)] for the month. A new month copies
    names and goals from the latest earlier month (or uses the defaults)."""
    with Session() as s:
        rows = list(s.scalars(
            select(Habit).where(Habit.year == year, Habit.month == month)
            .order_by(Habit.slot)
        ))
        if not rows:
            key = Habit.year * 12 + Habit.month
            prev = s.execute(
                select(Habit.year, Habit.month)
                .where(key < year * 12 + month)
                .order_by(key.desc()).limit(1)
            ).first()
            if prev:
                old = [(h.name, h.goal) for h in s.scalars(
                    select(Habit).where(Habit.year == prev[0], Habit.month == prev[1])
                    .order_by(Habit.slot)
                )]
            else:
                old = [(n, 20) for n in DEFAULT_HABITS]
            old = (old + [("", 20)] * NUM_HABITS)[:NUM_HABITS]
            rows = [Habit(year=year, month=month, slot=i + 1, name=n, goal=g)
                    for i, (n, g) in enumerate(old)]
            s.add_all(rows)
            s.commit()
        return [(h.id, h.slot, h.name, h.goal) for h in rows]


def update_habit(habit_id: int, name: str, goal: int):
    with Session() as s:
        habit = s.get(Habit, habit_id)
        habit.name = name.strip()
        habit.goal = int(goal)
        s.commit()


def get_month_checks(year: int, month: int) -> dict[int, set[int]]:
    """Return {habit_id: {day numbers that are ticked}} for the month."""
    last = calendar.monthrange(year, month)[1]
    with Session() as s:
        rows = s.execute(
            select(HabitLog.habit_id, HabitLog.log_date)
            .join(Habit, Habit.id == HabitLog.habit_id)
            .where(HabitLog.log_date >= date(year, month, 1),
                   HabitLog.log_date <= date(year, month, last))
        ).all()
    checks: dict[int, set[int]] = {}
    for habit_id, log_date in rows:
        checks.setdefault(habit_id, set()).add(log_date.day)
    return checks


def save_month_checks(year: int, month: int, checks: dict[int, set[int]]):
    """Replace the month's ticks with the given {habit_id: {days}}."""
    last = calendar.monthrange(year, month)[1]
    with Session() as s:
        s.execute(delete(HabitLog).where(
            HabitLog.habit_id.in_(list(checks)),
            HabitLog.log_date >= date(year, month, 1),
            HabitLog.log_date <= date(year, month, last),
        ))
        s.add_all(
            HabitLog(habit_id=hid, log_date=date(year, month, d))
            for hid, days in checks.items() for d in days
        )
        s.commit()
def get_history_df() -> pd.DataFrame:
    """One row per habit per day up to today: habit, date, done (1 or 0)."""
    today = date.today()
    with Session() as s:
        habits = s.execute(select(Habit.id, Habit.year, Habit.month, Habit.name)).all()
        ticks = {(hid, d) for hid, d in s.execute(
            select(HabitLog.habit_id, HabitLog.log_date))}
    if not ticks:  # nothing ticked yet, so nothing to learn from
        return pd.DataFrame({"habit": [], "date": pd.to_datetime([]), "done": []})
    first_day = min(d for _, d in ticks)  # the day you started tracking
    rows = []
    for hid, year, month, name in habits:
        if not name.strip():
            continue
        for day in range(1, calendar.monthrange(year, month)[1] + 1):
            d = date(year, month, day)
            if d > today:
                break
            if d >= first_day:
                rows.append((name.strip(), d, int((hid, d) in ticks)))
    df = pd.DataFrame(rows, columns=["habit", "date", "done"])
    df["date"] = pd.to_datetime(df["date"])
    return df
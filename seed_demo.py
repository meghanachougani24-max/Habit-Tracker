"""Fills a SEPARATE demo database (demo.db) with ~75 days of realistic ticks,
so you can see streaks and the AI model working. Your real habits.db is untouched.

Run:  python seed_demo.py
"""
import os

os.environ["HABIT_DB"] = "demo.db"  # must be set BEFORE importing db

import random
from datetime import date, timedelta

from db import get_month_habits, init_db, save_month_checks

random.seed(11)
init_db()

# chance of doing each habit on weekdays / weekends (+ extra if done yesterday)
PROFILE = {
    "Drink water": (0.90, 0.85), "Workout": (0.80, 0.20),
    "Read 20 minutes": (0.55, 0.50), "Meditate": (0.50, 0.50),
    "Sleep early": (0.70, 0.30), "Journal": (0.55, 0.55),
    "Walk 10k steps": (0.40, 0.80), "No junk food": (0.60, 0.40),
    "Study": (0.75, 0.35), "Stretch": (0.30, 0.30),
}

today = date.today()
start = today - timedelta(days=75)
ticks = {}  # (year, month) -> {habit name: set(days)}
last_done = {name: False for name in PROFILE}
d = start
while d < today:  # up to yesterday, so "today" is still open
    for name, (weekday_p, weekend_p) in PROFILE.items():
        p = weekday_p if d.weekday() < 5 else weekend_p
        p = min(0.95, p + (0.15 if last_done[name] else -0.10))  # streaky behaviour
        done = random.random() < p
        last_done[name] = done
        if done:
            ticks.setdefault((d.year, d.month), {}).setdefault(name, set()).add(d.day)
    d += timedelta(days=1)

months = sorted({(start.year, start.month), (today.year, today.month)}
                | set(ticks))
for year, month in months:
    habits = get_month_habits(year, month)
    checks = {hid: ticks.get((year, month), {}).get(name, set())
              for hid, _slot, name, _goal in habits}
    save_month_checks(year, month, checks)

print("Demo data saved in demo.db. To view it, add this line to your .env file:")
print("HABIT_DB=demo.db")
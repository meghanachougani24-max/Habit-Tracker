from datetime import date

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

FEATURES = ["dow", "prev_done", "rate_7", "streak", "habit_rate", "dow_rate"]
MIN_DAYS = 14  # days of history needed before the model switches on


def _daily(history: pd.DataFrame, today: pd.Timestamp) -> pd.DataFrame:
    """One row per habit per day, no gaps, from the habit's first day to today.
    The same habit name (any capitals) is treated as one habit."""
    parts = []
    key = history["habit"].str.strip().str.lower()
    for _, g in history.groupby(key):
        name = g.sort_values("date")["habit"].iloc[-1]
        per_day = g.groupby("date")["done"].max()
        full = pd.date_range(per_day.index.min(), today)
        per_day = per_day.reindex(full, fill_value=0)
        parts.append(pd.DataFrame(
            {"habit": name, "date": full, "done": per_day.values}))
    return pd.concat(parts, ignore_index=True)


def _features(daily: pd.DataFrame) -> pd.DataFrame:
    """Facts known BEFORE each day (so the model can't peek at the answer)."""
    parts = []
    for _, g in daily.groupby("habit"):
        g = g.sort_values("date").copy()
        prev = g["done"].shift(1)
        p0 = prev.fillna(0)
        g["has_prev"] = prev.notna()
        g["dow"] = g["date"].dt.dayofweek
        g["prev_done"] = p0
        g["rate_7"] = prev.rolling(7, min_periods=1).mean().fillna(0)
        g["streak"] = p0.groupby((p0 == 0).cumsum()).cumsum()
        g["habit_rate"] = prev.expanding().mean().fillna(0)
        # how often this habit was done on the same weekday before
        same_day = g.groupby("dow")["done"].transform(
            lambda s: s.shift(1).expanding().mean())
        g["dow_rate"] = same_day.fillna(g["habit_rate"])
        parts.append(g)
    return pd.concat(parts, ignore_index=True)


def streaks(history: pd.DataFrame, today=None) -> pd.DataFrame:
    """Current and best streak (in days) for every habit."""
    today = pd.Timestamp(today or date.today())
    out = []
    for habit, g in _daily(history, today).groupby("habit"):
        done = g.sort_values("date")["done"].tolist()
        best = run = 0
        for v in done:
            run = run + 1 if v else 0
            best = max(best, run)
        if not done[-1]:          # today isn't finished yet, don't break the streak
            done = done[:-1]
        current = 0
        for v in reversed(done):
            if not v:
                break
            current += 1
        out.append({"Habit": habit, "Current streak": current, "Best streak": best})
    return (pd.DataFrame(out)
            .sort_values(["Current streak", "Best streak"], ascending=False)
            .reset_index(drop=True))


def predict_today(history: pd.DataFrame, today=None):
    """Train on past days, then estimate the chance of doing each habit today.
    Returns (table, info). table is empty until there is enough history."""
    today = pd.Timestamp(today or date.today())
    daily = _features(_daily(history, today))
    train = daily[(daily["date"] < today) & daily["has_prev"]]
    now = daily[daily["date"] == today]
    n_days = train["date"].nunique()
    info = {"ready": False, "days": n_days, "accuracy": None, "baseline": None}

    if n_days < MIN_DAYS or train["done"].nunique() < 2:
        return pd.DataFrame(), info

    def new_model():
        return RandomForestClassifier(
            n_estimators=100, min_samples_leaf=3, random_state=42)

    # Honest check: learn from the older 75% of days, test on the newest 25%.
    days = np.sort(train["date"].unique())
    cut = days[int(len(days) * 0.75)]
    old, new = train[train["date"] < cut], train[train["date"] >= cut]
    if old["done"].nunique() == 2 and len(new) > 0:
        check = new_model().fit(old[FEATURES], old["done"])
        info["accuracy"] = float((check.predict(new[FEATURES]) == new["done"]).mean())
        majority = int(old["done"].mean() >= 0.5)   # "always guess the common answer"
        info["baseline"] = float((new["done"] == majority).mean())

    model = new_model().fit(train[FEATURES], train["done"])
    chance = model.predict_proba(now[FEATURES])[:, list(model.classes_).index(1)]
    table = pd.DataFrame({
        "Habit": now["habit"].values,
        "Chance (%)": (chance * 100).round().astype(int),
        "Done today": now["done"].astype(bool).values,
    })
    info["ready"] = True
    return table.sort_values("Chance (%)").reset_index(drop=True), info
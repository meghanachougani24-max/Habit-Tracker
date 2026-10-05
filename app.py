import calendar
from datetime import date

import altair as alt
import pandas as pd
import streamlit as st

from db import (get_history_df, get_month_checks, get_month_habits, init_db,
                save_month_checks, update_habit)
from ml import MIN_DAYS, predict_today, streaks

st.set_page_config(page_title="AI Habit Tracker", page_icon="✅", layout="wide")
init_db()

WEEK_COLORS = ["#5b8def", "#f06ea9", "#3fbfb5", "#f5a742", "#5b8def"]
TRACK = "#e6ecf8"
MONTHS = list(calendar.month_name)[1:]
today = date.today()


# ---------- helpers ----------
def on_grid_edit(key, year, month, habits):
    """Runs right after you tick a box: saves the change to the database."""
    edits = st.session_state[key]["edited_rows"]
    checks = get_month_checks(year, month)
    for row, changes in edits.items():
        habit_id = habits[int(row)][0]
        ticked_days = checks.setdefault(habit_id, set())
        for col, ticked in changes.items():
            if ticked:
                ticked_days.add(int(col))
            else:
                ticked_days.discard(int(col))
    save_month_checks(year, month, checks)


def donut(pct, color):
    df = pd.DataFrame({"part": ["Done", "Left"], "value": [pct, 100 - pct]})
    return (
        alt.Chart(df)
        .mark_arc(innerRadius=42, outerRadius=62)
        .encode(
            theta=alt.Theta("value:Q"),
            color=alt.Color(
                "part:N",
                scale=alt.Scale(domain=["Done", "Left"], range=[color, TRACK]),
                legend=None,
            ),
        )
        .properties(width=140, height=140)
    )


# ---------- header: pick the month (every month is its own sheet) ----------
st.title("✅ AI Habit Tracker")
c1, c2, _ = st.columns([2, 1, 5])
month_name = c1.selectbox("Month", MONTHS, index=today.month - 1)
year = int(c2.number_input("Year", 2020, 2100, today.year, step=1))
month = MONTHS.index(month_name) + 1
n_days = calendar.monthrange(year, month)[1]
days = list(range(1, n_days + 1))

habits = get_month_habits(year, month)  # [(id, slot, name, goal)]
checks = get_month_checks(year, month)  # {habit_id: {ticked days}}

# ---------- edit the 10 habits ----------
with st.expander("✏️ Edit my 10 habits and goals"):
    with st.form(f"habits_{year}_{month}"):
        h1, h2 = st.columns([4, 1])
        h1.caption("Habit")
        h2.caption("Goal (days)")
        new_values = []
        for habit_id, slot, name, goal in habits:
            a, b = st.columns([4, 1])
            new_name = a.text_input(
                f"Habit {slot}", value=name, placeholder=f"Habit {slot}",
                key=f"name_{year}_{month}_{slot}", label_visibility="collapsed",
            )
            new_goal = b.number_input(
                f"Goal {slot}", 1, 31, min(goal, 31),
                key=f"goal_{year}_{month}_{slot}", label_visibility="collapsed",
            )
            new_values.append((habit_id, new_name, new_goal))
        if st.form_submit_button("Save habits"):
            for habit_id, new_name, new_goal in new_values:
                update_habit(habit_id, new_name, new_goal)
            st.rerun()

# ---------- numbers behind the charts ----------
active = [h for h in habits if h[2].strip()]
active_ids = [h[0] for h in active]
total = len(active)
done_per_day = {d: sum(d in checks.get(i, ()) for i in active_ids) for d in days}
pct_per_day = {d: (100 * done_per_day[d] / total if total else 0) for d in days}

# ---------- daily completion chart ----------
st.subheader(f"{month_name} {year}")
daily = pd.DataFrame({
    "Day": days,
    "Done": [done_per_day[d] for d in days],
    "Percent": [round(pct_per_day[d]) for d in days],
})
st.altair_chart(
    alt.Chart(daily)
    .mark_area(line={"color": "#5b8def"}, color="#5b8def", opacity=0.2,
               interpolate="monotone")
    .encode(
        x=alt.X("Day:Q", scale=alt.Scale(domain=[1, n_days], nice=False),
                axis=alt.Axis(tickMinStep=1, title=None)),
        y=alt.Y("Percent:Q", scale=alt.Scale(domain=[0, 100]),
                title="Habits done (%)"),
        tooltip=["Day", "Done", "Percent"],
    )
    .properties(height=200),
    use_container_width=True,
)

# ---------- weekly donuts ----------
weeks = [days[i:i + 7] for i in range(0, n_days, 7)]
for col, wk, color, num in zip(st.columns(len(weeks)), weeks, WEEK_COLORS, range(1, 6)):
    week_pct = (
        100 * sum(done_per_day[d] for d in wk) / (total * len(wk)) if total else 0
    )
    with col:
        st.altair_chart(donut(week_pct, color), use_container_width=False)
        st.metric(f"Week {num}", f"{week_pct:.1f}%")

# ---------- the tick grid ----------
st.subheader("Daily habits")
rows = {}
for habit_id, slot, name, goal in habits:
    label = f"{slot}. {name}" if name.strip() else f"{slot}."
    rows[label] = [d in checks.get(habit_id, ()) for d in days]
grid = pd.DataFrame(rows, index=[str(d) for d in days]).T  # habits x days

config = {}
for d in days:
    weekday = calendar.day_abbr[date(year, month, d).weekday()][:2]
    config[str(d)] = st.column_config.CheckboxColumn(f"{weekday} {d}", width="small")

grid_key = f"grid_{year}_{month}"
st.data_editor(
    grid,
    column_config=config,
    use_container_width=True,
    key=grid_key,
    on_change=on_grid_edit,
    args=(grid_key, year, month, habits),
)

# ---------- monthly summary: goal vs done ----------
st.subheader("Monthly progress")
if not active:
    st.info("Add your habit names in 'Edit my 10 habits and goals' above.")
else:
    summary = pd.DataFrame({
        "Habit": [h[2] for h in active],
        "Goal": [h[3] for h in active],
        "Done": [len(checks.get(h[0], ())) for h in active],
    })
    summary["Percent"] = (100 * summary["Done"] / summary["Goal"]).round()
    st.dataframe(
        summary,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Percent": st.column_config.ProgressColumn(
                "Percent", min_value=0, max_value=100, format="%d%%"
            )
        },
    )
    # ---------- AI insights (uses all your history up to today) ----------
st.divider()
st.header("🤖 AI insights")
history = get_history_df()
if history.empty:
    st.info("Tick a few habits and your streaks and predictions will appear here.")
else:
    left, right = st.columns(2)
    with left:
        st.subheader("Streaks")
        st.dataframe(streaks(history), hide_index=True, use_container_width=True)
    with right:
        st.subheader("Habits at risk today")
        risk, info = predict_today(history)
        if not info["ready"]:
            st.info(
                f"The model needs at least {MIN_DAYS} days of history with both "
                f"done and missed days. You have {info['days']} so far. Keep ticking!"
            )
        else:
            todo = risk[~risk["Done today"]].drop(columns="Done today")
            if todo.empty:
                st.success("All habits done today. Great job! 🎉")
            else:
                st.dataframe(
                    todo, hide_index=True, use_container_width=True,
                    column_config={"Chance (%)": st.column_config.ProgressColumn(
                        "Chance of doing it today", min_value=0, max_value=100,
                        format="%d%%")},
                )
            if info["accuracy"] is not None:
                st.caption(
                    f"Random forest trained on {info['days']} days. On the newest "
                    f"days it was right {info['accuracy']:.0%} of the time, versus "
                    f"{info['baseline']:.0%} for always guessing the most common answer."
                )
# AI Habit Tracker

A monthly habit tracker built with Streamlit. Each month is its own sheet with
10 habits you choose, a daily tick grid, weekly progress donuts and goal tracking.

![Monthly view](assets/monthly-view.png)

## Features
- One sheet per month (month and year picker)
- 10 editable habits with a monthly goal for each
- Tick grid for every day of the month, saved instantly
- Daily completion chart and weekly progress donuts
- Monthly progress table (goal vs done)
- New months copy the previous month's habits

## Tech stack
Python 3.12, Streamlit 1.40.1, pandas, NumPy, SQLAlchemy with SQLite, scikit-learn

## Installation
```bash
git clone https://github.com/<your-username>/habit-tracker.git
cd habit-tracker
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```
On Mac/Linux, use `python3.12 -m venv .venv` and `source .venv/bin/activate`.

## API / model setup
No API key is needed right now. If an LLM coach is added later, put the key in a
`.env` file (never commit it).

## Run
```bash
streamlit run app.py
```

## Project structure
```
app.py            Streamlit interface
db.py             SQLite database (SQLAlchemy)
requirements.txt  Pinned dependencies
```

## Limitations
- Stored locally in SQLite, so there is no multi-user support or login
- Habit names are edited in a form, not inside the grid
- The AI features (streaks and a miss-prediction model) are still in progress
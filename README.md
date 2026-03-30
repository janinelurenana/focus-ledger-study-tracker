# 📚 FocusLedger - Study Tracker

A full-stack personal study tracking application built in Python — from a CLI prototype to a deployed Streamlit web app backed by SQLite.

Built as a learning project to practice software engineering fundamentals: layered architecture, relational databases, data analysis, and data visualization.

**Live demo:** [focus-ledger-study-tracker-igeiwsearuih3zwpuxpbm4.streamlit.app](https://focus-ledger-study-tracker-igeiwsearuih3zwpuxpbm4.streamlit.app/)

---

## Features

**Logging**
- Log study sessions with subject, start time, end time, and notes
- Hours calculated automatically from start and end time
- Overlap detection warns if a new session conflicts with an existing one
- Audit trail — every entry stores a `created_at` timestamp that never changes

**Study Plans**
- Create plans with a subject, goal, target hours, and due date
- Mark plans as complete — completion date is recorded automatically
- Edit target hours, due date, or goal on pending plans
- Overdue warning banner shown across all pages

**Analysis**
- Total hours per subject
- Weekly study totals
- Average session and daily study time
- Study streak tracker (current and longest)
- Plan completion rate
- Peak study hours — what time of day you study most
- Date range filter: last 7, 30, 60 days, or all time

**Visualization**
- Hours per subject (horizontal bar chart)
- Weekly totals (line + area chart)
- Study trend with 7-day rolling average
- Activity heatmap (GitHub contribution-style)
- Peak study hours by hour of day
- Full matplotlib dashboard rendered inline in Streamlit

**Data**
- SQLite backend with parameterized queries throughout
- Schema migration support for adding columns to existing databases
- Separate CLI (`study_tracker.py`) kept as a backup interface

---

## Tech Stack

| Layer | Technology |
|---|---|
| Web UI | Streamlit |
| Database | SQLite via `sqlite3` |
| Analysis | pandas, NumPy |
| Visualization | matplotlib |
| Language | Python 3.10+ |
| Deployment | Streamlit Community Cloud |

---

## Project Structure

```
focus-ledger-study-tracker/
├── app.py                  # Streamlit web app — entry point
├── database.py             # SQLite layer — all DB access goes here
├── analysis.py             # Data analysis functions (pandas/NumPy)
├── visualization.py        # Chart functions (matplotlib)
├── study_tracker.py        # Original CLI — kept as backup
├── test_study_tracker.py   # Unit tests (pytest)
├── requirements.txt
├── .gitignore
├── .streamlit/
|   └── config.toml
└── README.md
```

---

## Architecture

The project is built in layers — each layer has one job and doesn't reach past its neighbour:

```
app.py / study_tracker.py   ← UI layer (Streamlit or CLI)
        ↓
    analysis.py             ← analysis layer (pandas, NumPy)
    visualization.py        ← chart layer (matplotlib)
        ↓
    database.py             ← data layer (SQLite)
        ↓
  study_tracker.db          ← database file
```

`app.py` never touches SQLite directly. `analysis.py` never renders anything. `visualization.py` never reads from the database. Each file can be tested and reasoned about independently.

---

## Running Locally

**1. Clone the repo**
```bash
git clone https://github.com/janinelurenana/focus-ledger-study-tracker.git
cd study-tracker
```

**2. Create a virtual environment and install dependencies**
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**3. Run the Streamlit app**
```bash
streamlit run app.py
```

Opens at `http://localhost:8501`.

**4. Or run the CLI**
```bash
python study_tracker.py
```

---

## Running Tests

```bash
pip install pytest
python -m pytest test_study_tracker.py -v
```

34 test cases covering storage, ID generation, entry/plan validation, edit logic, overdue detection, overlap detection, and analysis functions.

---

## Development Stages

This project was built incrementally across four stages:

| Stage | Description |
|---|---|
| 1 | CLI prototype — loops, functions, lists, dicts, CSV storage |
| 2 | SQLite migration — relational schema, parameterized queries, schema versioning |
| 3 | Data analysis — pandas, NumPy, date filtering, streak tracking |
| 4 | Visualization + Streamlit UI — matplotlib dashboard, web deployment |

---

## Known Limitations

- **No persistent storage on Streamlit Community Cloud** — SQLite lives in the container's temporary filesystem and resets on restart. For real persistence, the database layer would need to be swapped for a hosted database (e.g. Supabase/PostgreSQL).
- **Single user** — no authentication or per-user data isolation. Suitable for personal use; not designed for multiple users sharing one deployment.
- **No delete** — study entries are intentionally append-only (soft immutable audit trail). Corrections are made by adding a new entry.

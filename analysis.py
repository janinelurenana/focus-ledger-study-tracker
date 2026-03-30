"""
analysis.py — Stage 3: Data Analysis
Reads from SQLite via database.py into pandas DataFrames.
All analysis logic is unchanged — only the data source swapped.
"""

import numpy as np
import pandas as pd

import database


# ── Data loading ──────────────────────────────────────────────────────────────

def load_entries() -> pd.DataFrame:
    """
    Load study_entries from SQLite into a DataFrame.
    - 'date'  is parsed as datetime
    - 'hours' is coerced to float (bad values become NaN, then 0)
    """
    conn = database.get_connection()
    try:
        df = pd.read_sql_query(
            "SELECT * FROM study_entries ORDER BY date ASC, id ASC",
            conn
        )
    finally:
        conn.close()

    if df.empty:
        return df

    df["date"]  = pd.to_datetime(df["date"], errors="coerce")
    df["hours"] = pd.to_numeric(df["hours"], errors="coerce").fillna(0)
    return df


def load_plans() -> pd.DataFrame:
    """Load study_plans from SQLite into a DataFrame."""
    conn = database.get_connection()
    try:
        df = pd.read_sql_query(
            "SELECT * FROM study_plans ORDER BY id ASC",
            conn
        )
    finally:
        conn.close()

    if df.empty:
        return df

    df["due_date"]       = pd.to_datetime(df["due_date"], errors="coerce")
    df["completed_date"] = pd.to_datetime(df["completed_date"], errors="coerce")
    df["target_hours"]   = pd.to_numeric(df["target_hours"], errors="coerce").fillna(0)
    return df


def load_combined(since=None) -> pd.DataFrame:
    """
    Merge study entries and completed plans into one unified DataFrame
    with columns: date, subject, hours, source.

    - Entries    -> date = entry date,      hours = logged hours
    - Comp.plans -> date = completed_date,  hours = target_hours

    Args:
        since: optional pd.Timestamp or date. When provided, only rows
               on or after this date are returned. Pass None for all time.
    """
    frames = []

    # Study entries
    entries = load_entries()
    if not entries.empty:
        e = entries[["date", "subject", "hours"]].copy()
        e["source"] = "entry"
        frames.append(e)

    # Completed plans
    plans = load_plans()
    if not plans.empty:
        completed = plans[
            (plans["status"] == "completed") &
            (plans["completed_date"].notna())
        ].copy()

        if not completed.empty:
            p = completed.rename(columns={
                "completed_date": "date",
                "target_hours"  : "hours",
            })[["date", "subject", "hours"]]
            p["source"] = "plan"
            frames.append(p)

    if not frames:
        return pd.DataFrame(columns=["date", "subject", "hours", "source"])

    combined = pd.concat(frames, ignore_index=True)
    combined["date"]  = pd.to_datetime(combined["date"], errors="coerce")
    combined["hours"] = pd.to_numeric(combined["hours"], errors="coerce").fillna(0)

    # Apply date filter
    if since is not None:
        combined = combined[combined["date"] >= pd.Timestamp(since)]

    return combined


def _require_data(df: pd.DataFrame, feature: str) -> bool:
    """Return False and print a message if the DataFrame is empty."""
    if df.empty:
        print(f"  No data found for {feature}.\n")
        return False
    return True


# ── Feature 1: Total hours per subject ───────────────────────────────────────

def hours_per_subject(since=None):
    """
    Returns a Series: index = subject, values = total hours (descending).
    Includes both study entries and completed plans.
    """
    df = load_combined(since)
    if not _require_data(df, "hours per subject"):
        return None

    result = (
        df.groupby("subject")["hours"]
          .sum()
          .sort_values(ascending=False)
    )
    return result


def print_hours_per_subject(since=None):
    result = hours_per_subject(since)
    if result is None:
        return

    print("  -- Total hours per subject --")
    for subject, total in result.items():
        bar = "#" * int(total)
        print(f"  {subject:<20} {total:>5.1f} h  {bar}")
    print()


# ── Feature 2: Weekly study totals ───────────────────────────────────────────

def weekly_totals(since=None):
    """
    Returns a Series: index = week start (Monday), values = total hours.
    Uses pandas .resample("W-MON") on the unified date column.
    """
    df = load_combined(since)
    if not _require_data(df, "weekly totals"):
        return None

    df = df.dropna(subset=["date"])

    result = (
        df.set_index("date")["hours"]
          .resample("W-MON", label="left", closed="left")
          .sum()
    )
    return result


def print_weekly_totals(since=None):
    result = weekly_totals(since)
    if result is None:
        return

    print("  -- Weekly study totals --")
    for week, total in result.items():
        label = week.strftime("Week of %b %d")
        bar   = "#" * int(total)
        print(f"  {label:<22} {total:>5.1f} h  {bar}")
    print()


# ── Feature 3: Average study time ────────────────────────────────────────────

def average_study_time(since=None):
    """
    Returns a dict with:
      - overall_avg : mean hours per session
      - subject_avg : Series of mean hours per subject
      - daily_avg   : mean hours per calendar day with any activity
    """
    df = load_combined(since)
    if not _require_data(df, "average study time"):
        return None

    overall_avg = float(np.mean(df["hours"]))

    subject_avg = (
        df.groupby("subject")["hours"]
          .mean()
          .sort_values(ascending=False)
    )

    daily_totals = (
        df.dropna(subset=["date"])
          .groupby("date")["hours"]
          .sum()
    )
    daily_avg = float(np.mean(daily_totals)) if not daily_totals.empty else 0.0

    return {
        "overall_avg": overall_avg,
        "subject_avg": subject_avg,
        "daily_avg"  : daily_avg,
    }


def print_average_study_time(since=None):
    result = average_study_time(since)
    if result is None:
        return

    print("  -- Average study time --")
    print(f"  Per session (overall) : {result['overall_avg']:.2f} h")
    print(f"  Per study day         : {result['daily_avg']:.2f} h")
    print()
    print("  Per subject (avg session):")
    for subject, avg in result["subject_avg"].items():
        print(f"    {subject:<20} {avg:.2f} h")
    print()


# ── Feature 4: Streak tracker ────────────────────────────────────────────────
# Note: streak always operates on full history regardless of filter —
# a streak is a property of your overall habit, not a windowed metric.

def streak():
    """
    Returns a dict with:
      - current  : consecutive days with activity ending today/yesterday
      - longest  : longest ever streak (full history, no filter)
      - last_date: date of the most recent activity
    """
    df = load_combined(since=None)   # always full history
    if not _require_data(df, "streak"):
        return None

    df = df.dropna(subset=["date"])
    if df.empty:
        return None

    study_dates = sorted(df["date"].dt.date.unique())
    today       = pd.Timestamp.today().date()

    # ── Longest streak ──
    # Start temp and longest both at 1 (a single day is always a streak of 1).
    # When a gap is found, update longest BEFORE resetting temp so we never
    # lose the count of an isolated run (e.g. [day1, day3, day5] → longest=1).
    longest = 1
    temp    = 1
    for i in range(1, len(study_dates)):
        gap = (study_dates[i] - study_dates[i - 1]).days
        if gap == 1:
            temp   += 1
            longest = max(longest, temp)
        else:
            longest = max(longest, temp)  # ← capture before reset
            temp    = 1
    longest = max(longest, temp)          # ← capture the final run

    # ── Current streak ──
    # Count backwards from the most recent date while days are consecutive.
    current = 1
    for i in range(len(study_dates) - 1, 0, -1):
        gap = (study_dates[i] - study_dates[i - 1]).days
        if gap == 1:
            current += 1
        else:
            break

    # If the most recent activity was more than 1 day ago, streak is broken.
    last_date  = study_dates[-1]
    days_since = (today - last_date).days
    if days_since > 1:
        current = 0

    return {
        "current"  : current,
        "longest"  : longest,
        "last_date": last_date,
    }


def print_streak():
    result = streak()
    if result is None:
        return

    flame = "🔥" * min(result["current"], 7)
    print("  -- Study streak (all time) --")
    print(f"  Current streak : {result['current']} day(s)  {flame}")
    print(f"  Longest streak : {result['longest']} day(s)")
    print(f"  Last studied   : {result['last_date']}")
    print()


# ── Feature 5: Plan completion rate ──────────────────────────────────────────
# Also always uses full history — pending/completed counts shouldn't be filtered.

def plan_completion_rate():
    """Returns a dict with total, completed, pending counts and completion %."""
    df = load_plans()
    if df.empty:
        print("  No study plans found for completion rate.\n")
        return None

    total     = len(df)
    completed = int((df["status"] == "completed").sum())
    pending   = total - completed
    rate      = (completed / total * 100) if total > 0 else 0.0

    return {
        "total"    : total,
        "completed": completed,
        "pending"  : pending,
        "rate"     : rate,
    }


def print_plan_completion_rate():
    result = plan_completion_rate()
    if result is None:
        return

    filled = int(result["rate"] / 5)
    empty  = 20 - filled
    bar    = "#" * filled + "." * empty

    print("  -- Plan completion rate (all time) --")
    print(f"  [{bar}] {result['rate']:.0f}%")
    print(f"  {result['completed']} of {result['total']} plans completed  "
          f"({result['pending']} pending)")
    print()


# ── Feature 6: Peak study hours ──────────────────────────────────────────────

def peak_study_hours(since=None):
    """
    Returns a Series: index = hour of day (0-23), values = total hours studied.
    Derived from start_time on each entry.
    Used to answer: what time of day does the user study most?
    """
    conn = database.get_connection()
    try:
        df = pd.read_sql_query(
            "SELECT start_time, hours, date FROM study_entries",
            conn
        )
    finally:
        conn.close()

    if df.empty:
        return None

    df["hours"] = pd.to_numeric(df["hours"], errors="coerce").fillna(0)

    # Apply date filter if provided
    if since is not None:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df[df["date"] >= pd.Timestamp(since)]

    if df.empty:
        return None

    # Extract the hour from start_time string "HH:MM"
    df["hour"] = df["start_time"].str.extract(r"^(\d{1,2}):").astype(float)
    df = df.dropna(subset=["hour"])
    df["hour"] = df["hour"].astype(int)

    # Sum hours per hour-of-day, reindex to fill missing hours with 0
    result = (
        df.groupby("hour")["hours"]
          .sum()
          .reindex(range(24), fill_value=0)
    )
    return result


def print_peak_study_hours(since=None):
    result = peak_study_hours(since)
    if result is None or result.sum() == 0:
        print("  No time-of-day data yet.\n")
        return

    print("  -- Peak study hours --")
    for hour, total in result.items():
        if total > 0:
            label = f"{hour:02d}:00"
            bar   = "#" * int(total * 4)   # scale: 4 chars per hour
            print(f"  {label}  {total:>5.2f}h  {bar}")
    print()


# ── Combined analytics summary ────────────────────────────────────────────────

def print_full_summary(since=None):
    print_hours_per_subject(since)
    print_weekly_totals(since)
    print_average_study_time(since)
    print_streak()
    print_plan_completion_rate()
    print_peak_study_hours(since)

